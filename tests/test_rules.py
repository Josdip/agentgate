import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agentgate.app import create_app
from agentgate.policy import ToolCall
from agentgate.rules import RuleChange, RuleSpec
from agentgate.store import Store

AGENT = "test-agent-credential-long-enough"
REVIEWER = "test-reviewer-credential-long-enough"


def auth(token=REVIEWER):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(str(tmp_path / "audit.db"), AGENT, REVIEWER)) as client:
        yield client


def rule(**changes):
    return {
        "name": "Support refunds",
        "tool": "refunds.create",
        "decision": "allow",
        "scope": ["T-1001", "T-1002"],
        "approval_threshold_cents": 10000,
        **changes,
    }


def refund(store, amount=2500):
    return store.submit(
        ToolCall(
            run_id="rules-test",
            tool="refunds.create",
            arguments={"ticket_id": "T-1001", "amount_cents": amount},
        )
    )


def test_default_rules_visible_with_controls_and_history(client):
    response = client.get("/api/agents/support-agent/rules", headers=auth())
    assert response.status_code == 200
    policy = response.json()
    assert policy["revision"] == 1 and len(policy["rules"]) == 3
    assert policy["history"][0]["changed_by"] == "system"
    assert len(policy["catalog"]) == 6
    assert client.get("/rules").status_code == 200


@pytest.mark.parametrize("token", [None, AGENT])
def test_agent_and_anonymous_cannot_read_or_change_rules(client, token):
    headers = auth(token) if token else {}
    base = "/api/agents/support-agent/rules"
    assert client.get(base, headers=headers).status_code == 401
    assert (
        client.post(base, json={"revision": 1, "rule": rule()}, headers=headers).status_code == 401
    )
    assert (
        client.put(
            base + "/default-refunds-create", json={"revision": 1, "rule": rule()}, headers=headers
        ).status_code
        == 401
    )
    assert (
        client.delete(base + "/default-refunds-create?revision=1", headers=headers).status_code
        == 401
    )


def test_add_rule_changes_real_decision_and_profile_for_only_one_agent(client):
    path = "/api/agents/sales-agent/rules"
    assert (
        client.post("/api/demo/scenarios/sales-refund/run", headers=auth()).json()["action"][
            "outcome"
        ]
        == "denied"
    )
    policy = client.post(path, json={"revision": 1, "rule": rule()}, headers=auth()).json()
    assert policy["revision"] == 2
    action = client.post("/api/demo/scenarios/sales-refund/run", headers=auth()).json()["action"]
    assert action["outcome"] == "executed" and action["policy_revision"] == 2
    assert action["matched_rule_id"]
    profile = client.get("/api/agents/sales-agent", headers=auth()).json()
    assert any(item["tool"] == "refunds.create" for item in profile["tools"])
    assert client.get("/api/agents/support-agent/rules", headers=auth()).json()["revision"] == 1
    assert policy["history"][0]["operation"] == "add"


def test_limit_edit_is_persistent_and_records_matched_revision(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    assert refund(store)["outcome"] == "executed"
    policy = store.change_rule(
        "support-agent",
        RuleChange(revision=1, rule=RuleSpec(**rule(approval_threshold_cents=1000))),
        rule_id="default-refunds-create",
    )
    assert policy["revision"] == 2
    action = refund(Store(store.path))
    assert action["outcome"] == "pending" and action["policy_revision"] == 2
    assert action["matched_rule_id"] == "default-refunds-create"
    assert policy["history"][0]["snapshot"] != policy["history"][1]["snapshot"]


def test_delete_fails_closed_and_is_not_reseeded_after_restart(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    policy = store.rules("support-agent")
    for entry in list(policy["rules"]):
        policy = store.change_rule(
            "support-agent", None, rule_id=entry["id"], revision=policy["revision"]
        )
    restarted = Store(store.path)
    assert restarted.rules("support-agent")["rules"] == []
    action = refund(restarted)
    assert action["outcome"] == "denied" and action["result"] is None
    assert action["matched_rule_id"] is None
    assert len(restarted.rules("support-agent")["history"]) == 4


def test_deny_scope_and_required_review_are_enforced(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    store.change_rule(
        "support-agent",
        RuleChange(
            revision=1,
            rule=RuleSpec(**rule(decision="deny", scope=[], approval_threshold_cents=None)),
        ),
        rule_id="default-refunds-create",
    )
    assert refund(store)["outcome"] == "denied"
    store.change_rule(
        "support-agent",
        RuleChange(
            revision=2, rule=RuleSpec(**rule(decision="review", approval_threshold_cents=None))
        ),
        rule_id="default-refunds-create",
    )
    assert refund(store, 1)["outcome"] == "pending"
    store.change_rule(
        "support-agent",
        RuleChange(revision=3, rule=RuleSpec(**rule(scope=["T-1002"]))),
        rule_id="default-refunds-create",
    )
    assert refund(store)["outcome"] == "denied"


def test_old_pending_approval_cannot_execute_after_permission_change(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    pending = refund(store, 25000)
    store.change_rule("support-agent", None, rule_id="default-refunds-create", revision=1)
    with pytest.raises(ValueError, match="Rules changed"):
        store.review(pending["id"], True)
    assert store.list()[0]["outcome"] == "pending"
    assert store.review(pending["id"], False)["outcome"] == "rejected"


def test_conflicts_unknown_ids_and_duplicate_tools_do_not_write(client):
    base = "/api/agents/support-agent/rules"
    assert (
        client.post(base, json={"revision": 1, "rule": rule()}, headers=auth()).status_code == 409
    )
    assert (
        client.put(
            base + "/missing", json={"revision": 1, "rule": rule()}, headers=auth()
        ).status_code
        == 404
    )
    assert (
        client.delete(base + "/default-refunds-create?revision=99", headers=auth()).status_code
        == 409
    )
    assert client.delete(base + "/default-refunds-create", headers=auth()).status_code == 422
    assert client.get("/api/agents/unknown/rules", headers=auth()).status_code == 404
    assert (
        client.put(
            "/api/agents/sales-agent/rules/default-refunds-create",
            json={"revision": 1, "rule": rule()},
            headers=auth(),
        ).status_code
        == 404
    )
    assert client.get(base, headers=auth()).json()["revision"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"tool": "shell.execute"},
        {"scope": ["*"]},
        {"scope": []},
        {"scope": ["T-1001", "T-1001"]},
        {"approval_threshold_cents": True},
        {"approval_threshold_cents": -1},
        {"approval_threshold_cents": 1000001},
        {"name": "   "},
        {"decision": "execute"},
        {"approval_threshold_cents": "100"},
        {"decision": "review"},
    ],
)
def test_rule_schema_rejects_bypasses(changes):
    with pytest.raises(ValidationError):
        RuleSpec(**rule(**changes))


def test_nonexistent_document_and_unknown_fields_are_rejected(client):
    base = "/api/agents/sales-agent/rules"
    spec = {
        "name": "Bad document",
        "tool": "documents.read",
        "decision": "allow",
        "scope": ["payroll"],
        "approval_threshold_cents": None,
    }
    assert client.post(base, json={"revision": 1, "rule": spec}, headers=auth()).status_code == 422
    assert (
        client.post(
            base,
            json={"revision": 1, "rule": {**rule(), "agent_id": "support-agent"}},
            headers=auth(),
        ).status_code
        == 422
    )


def test_pending_message_keeps_body_redacted(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    spec = RuleSpec(
        name="Review messages", tool="messages.send", decision="review", scope=["support-inbox"]
    )
    store.change_rule(
        "support-agent", RuleChange(revision=1, rule=spec), rule_id="default-messages-send"
    )
    action = store.submit(
        ToolCall(
            run_id="test",
            tool="messages.send",
            arguments={"destination": "support-inbox", "message": "synthetic-secret-value"},
        )
    )
    assert action["outcome"] == "pending"
    store.review(action["id"], True)
    assert "synthetic-secret-value" not in json.dumps(store.list())


def test_concurrent_rule_edits_have_one_winner(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    change = RuleChange(revision=1, rule=RuleSpec(**rule(approval_threshold_cents=0)))

    def save(_):
        try:
            store.change_rule("support-agent", change, rule_id="default-refunds-create")
            return "saved"
        except ValueError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(save, range(2))) == ["conflict", "saved"]
    assert len(store.rules("support-agent")["history"]) == 2


def test_rule_changes_and_submission_share_atomic_policy_snapshot(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    change = RuleChange(
        revision=1, rule=RuleSpec(**rule(decision="deny", scope=[], approval_threshold_cents=None))
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        mutation = pool.submit(
            store.change_rule, "support-agent", change, rule_id="default-refunds-create"
        )
        submitted = pool.submit(refund, store)
        action = submitted.result()
        mutation.result()
    assert (action["policy_revision"], action["outcome"]) in {(1, "executed"), (2, "denied")}


def test_legacy_actions_survive_migration_but_unversioned_approvals_fail_closed(tmp_path):
    store = Store(str(tmp_path / "audit.db"))
    action = refund(store, 25000)
    with store.connection() as db:
        db.execute("UPDATE actions SET policy_revision=NULL,matched_rule_id=NULL")
        db.execute("DROP TABLE policy_history")
        db.execute("DROP TABLE policy_rules")
        db.execute("DROP TABLE agent_policies")
    migrated = Store(store.path)
    assert migrated.list()[0]["id"] == action["id"]
    with pytest.raises(ValueError, match="Rules changed"):
        migrated.review(action["id"], True)
