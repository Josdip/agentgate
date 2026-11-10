from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from agentgate.app import create_app
from agentgate.policy import ToolCall
from agentgate.rules import RuleChange
from agentgate.security import ApplicabilityUpdate
from agentgate.store import Store

AGENT = "test-agent-credential-long-enough"
REVIEWER = "test-reviewer-credential-long-enough"
AUTH = {"Authorization": f"Bearer {REVIEWER}"}
URL = "/api/agents/support-agent/security"
SCOPE = "/api/agents/support-agent/compliance/gdpr"


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path / "audit.db"), AGENT, REVIEWER)) as client:
        yield client


@pytest.mark.parametrize("headers", [{}, {"Authorization": f"Bearer {AGENT}"}])
def test_assessments_and_scope_are_reviewer_only(client, headers):
    assert client.get(URL, headers=headers).status_code == 401
    assert client.put(SCOPE, headers=headers, json={}).status_code == 401


def test_unknown_scope_never_claims_compliance_or_cve_matches(client):
    response = client.get(URL, headers=AUTH)
    assert response.status_code == 200
    report = response.json()
    assert report["activity"] == {"total": 0, "denied": 0, "pending": 0, "executed": 0}
    assert {f["id"] for f in report["frameworks"]} == {"gdpr", "hipaa", "eu-ai-act"}
    assert all(f["applicability"] == "unknown" for f in report["frameworks"])
    assert all(f["compliance_status"] == "Not assessed" for f in report["frameworks"])
    assert {f["id"] for f in report["findings"]} >= {"inventory", "injection", "budget"}
    assert not any(f["kind"].startswith("Observed") for f in report["findings"])
    assert client.get("/security").status_code == 200
    assert client.get("/api/agents/no-such-agent/security", headers=AUTH).status_code == 404


def test_applicability_is_versioned_but_cannot_assert_compliance(client):
    update = {
        "revision": 0,
        "applicability": "applies",
        "rationale": "Demo workflow uses EU personal data.",
    }
    result = client.put(SCOPE, json=update, headers=AUTH)
    assert result.status_code == 200
    gdpr = result.json()["frameworks"][0]
    assert gdpr["revision"] == 1 and gdpr["applicability"] == "applies"
    assert gdpr["compliance_status"] == "Not assessed"
    assert client.put(SCOPE, json=update, headers=AUTH).status_code == 409
    assert client.put(SCOPE, json={**update, "compliant": True}, headers=AUTH).status_code == 422
    assert (
        client.put(SCOPE, json={**update, "applicability": "compliant"}, headers=AUTH).status_code
        == 422
    )
    assert client.put(SCOPE, json={**update, "rationale": " "}, headers=AUTH).status_code == 422
    assert client.put(SCOPE + "-unknown", json=update, headers=AUTH).status_code == 404
    sales = client.get("/api/agents/sales-agent/security", headers=AUTH).json()
    assert sales["frameworks"][0]["revision"] == 0
    assert client.get("/api/agents/support-agent/rules", headers=AUTH).json()["revision"] == 1


def test_scope_history_survives_restart_and_concurrent_edits(tmp_path):
    path = str(tmp_path / "audit.db")
    store = Store(path)
    update = ApplicabilityUpdate(
        revision=0,
        applicability="not_applicable",
        rationale="Synthetic demo contains no personal data.",
    )

    def save():
        try:
            store.update_compliance_scope("support-agent", "gdpr", update)
            return "saved"
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: save(), range(2))) == ["conflict", "saved"]
    restarted = Store(path)
    assert restarted.security("support-agent")["frameworks"][0]["applicability"] == "not_applicable"
    with restarted.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM compliance_scope_history").fetchone()[0] == 1


def test_rule_fix_removes_exposure_without_erasing_attempts(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    store.submit(
        ToolCall(
            run_id="blocked", tool="unknown.execute", arguments={"secret": "not-for-security-page"}
        )
    )
    store.submit(
        ToolCall(
            run_id="pending",
            tool="refunds.create",
            arguments={"ticket_id": "T-1001", "amount_cents": 25000},
        )
    )
    initial = store.security("support-agent")
    assert {f["id"] for f in initial["findings"]} >= {"blocked", "pending"}
    assert "not-for-security-page" not in str(initial)
    policy = store.rules("support-agent")
    monetary = next(rule for rule in policy["rules"] if rule["tool"] == "refunds.create")
    change = {key: value for key, value in monetary.items() if key != "id"}
    store.change_rule(
        "support-agent",
        RuleChange(
            revision=1, rule={**change, "decision": "review", "approval_threshold_cents": None}
        ),
        rule_id=monetary["id"],
    )
    fixed = store.security("support-agent")
    assert fixed["policy_revision"] == 2
    assert not any(f["id"].startswith("automatic-") for f in fixed["findings"])
    assert {f["id"] for f in fixed["findings"]} >= {"blocked", "budget", "pending"}
    assert fixed["controls"][1]["status"] == "Present in gateway"
    assert store.security("sales-agent")["activity"]["total"] == 0


def test_counts_cover_all_rows_and_evidence_is_bounded(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    for i in range(205):
        store.submit(ToolCall(run_id=f"blocked-{i}", tool="unknown.execute", arguments={}))
    report = store.security("support-agent")
    assert report["activity"]["denied"] == 205
    assert len(report["recent_evidence"]) == 5
