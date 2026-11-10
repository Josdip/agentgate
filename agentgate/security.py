"""Versioned curated checks, not legal determinations or a vulnerability scanner."""

from typing import Literal

from pydantic import Field

from .policy import StrictModel

CATALOG_VERSION = "2026-11-10.1"
FRAMEWORKS = {
    "gdpr": {
        "name": "GDPR",
        "focus": "Personal data protection",
        "scope": "Review territorial scope and whether this workflow processes personal data. Agent location alone does not determine applicability.",
        "reference": "Articles 3, 5, 25 and 32",
        "source": "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        "next_steps": "Document lawful basis, data flows, minimisation, retention, rights handling and processor arrangements. Assess whether a data protection impact assessment is required.",
    },
    "hipaa": {
        "name": "HIPAA Security Rule",
        "focus": "Electronic protected health information",
        "scope": "Review whether the business is a covered entity or business associate and whether this workflow handles electronic protected health information.",
        "reference": "45 CFR 164.308 and 164.312",
        "source": "https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html",
        "next_steps": "Complete a documented ePHI risk analysis, verify access and audit safeguards, review business associate agreements and establish incident procedures.",
    },
    "eu-ai-act": {
        "name": "EU AI Act",
        "focus": "AI use, role and risk classification",
        "scope": "Review territorial scope, provider/deployer role and intended use. A support, sales or finance label does not establish a high-risk classification.",
        "reference": "Risk classification; Article 26 where applicable",
        "source": "https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai",
        "next_steps": "Classify the actual use case, check prohibited practices and relevant transparency/literacy duties, and confirm applicable dates. For high-risk uses, review oversight, monitoring and logging obligations.",
    },
}
SOURCES = {
    "agency": "https://genai.owasp.org/llmrisk/llm062025-excessive-agency/",
    "injection": "https://genai.owasp.org/llmrisk/llm01-prompt-injection/",
}


class ApplicabilityUpdate(StrictModel):
    revision: int = Field(ge=0)
    applicability: Literal["unknown", "applies", "not_applicable"]
    rationale: str = Field(min_length=10, max_length=500)


def assess(policy, metadata, activity, latest):
    """Only use stored configuration and aggregate gateway evidence."""
    findings = []

    def add(key, title, severity, kind, evidence, fix, verify, source):
        findings.append(
            {
                "id": key,
                "title": title,
                "severity": severity,
                "kind": kind,
                "evidence": evidence,
                "fix": fix,
                "verification": verify,
                "source": source,
            }
        )

    active = [rule for rule in policy["rules"] if rule["decision"] != "deny"]
    money = [rule for rule in active if rule["tool"] in {"refunds.create", "payments.create"}]
    automatic = [
        rule
        for rule in money
        if rule["decision"] == "allow" and rule["approval_threshold_cents"] > 0
    ]
    for rule in automatic:
        add(
            "automatic-" + rule["id"],
            "Money can move without individual review",
            "medium",
            "Configured exposure",
            f"{rule['tool']} allows up to ${rule['approval_threshold_cents'] / 100:,.2f} per request under policy revision {policy['revision']}.",
            "If individual approval is required, change this rule to Require review or set the automatic limit to 0. Keep only necessary targets.",
            "Save the rule and run a small refund or payment case; it should await review.",
            SOURCES["agency"],
        )
    if money:
        add(
            "budget",
            "Repeated requests have no cumulative spending cap",
            "medium",
            "Known control gap",
            "The gateway limits each request separately; it does not track a daily or customer spending budget.",
            "Require review for all monetary actions as an interim measure. Add a transactional cumulative budget before connecting real payment tools.",
            "After budget enforcement is implemented, test split requests and concurrent requests against the same budget.",
            SOURCES["agency"],
        )
    if active:
        add(
            "injection",
            "Prompt-injection resistance has not been tested",
            "unknown",
            "Missing evidence",
            "Active tool access exists, but this scripted demo has no live model or adversarial model evaluation.",
            "Keep tool execution behind the gateway, minimise access and test untrusted messages and retrieved content with the real adapter.",
            "Run adversarial evaluations and confirm prohibited tool calls remain blocked. A blocked call alone does not prove injection detection.",
            SOURCES["injection"],
        )
    add(
        "inventory",
        "Live model and dependency evidence is missing",
        "unknown",
        "Missing evidence",
        f"{len(metadata.get('model_connections', []))} declared model entries; none is verified. Runtime packages and versions are not collected.",
        "Verify the actual model, tool and dependency versions when attaching a real agent. Compare exact versions with vendor advisories.",
        "Capture connector provenance and version evidence; reassess affected advisories. No CVE match is claimed here.",
        SOURCES["agency"],
    )
    if activity["denied"]:
        add(
            "blocked",
            "Requests tried to exceed approved access",
            "medium",
            "Observed attempt · blocked",
            f"Blocked requests: {activity['denied']}. These are synthetic attempts, not confirmed compromise.",
            "Inspect blocked requests in Activity. Correct the agent instructions or reduce its access; do not expand a rule simply to remove an alert.",
            "Rerun the relevant case after the change and inspect the decision. Historical blocked attempts remain evidence.",
            SOURCES["agency"],
        )
    if activity["pending"]:
        add(
            "pending",
            "Sensitive requests are waiting for review",
            "low",
            "Observed attempt · paused",
            f"{activity['pending']} requests are currently pending; they have not executed.",
            "Review the request and policy reason in Activity. Reject unexpected actions. Changed policies require rejection and resubmission of older pending requests.",
            "Confirm each pending request becomes rejected or executes only after an authorised approval.",
            SOURCES["agency"],
        )
    controls = [
        {
            "name": "Tool access boundaries",
            "status": "Present in gateway",
            "evidence": f"Policy revision {policy['revision']}; exact targets and default deny. Only gateway-routed synthetic actions are covered.",
        },
        {
            "name": "Demo baseline: review every monetary action",
            "status": "Gap" if automatic else "Present in gateway",
            "evidence": "Automatic monetary permissions exist. Individual review is a demo baseline, not a universal legal requirement."
            if automatic
            else "Monetary tools are blocked, absent, or require review for every positive amount.",
        },
        {
            "name": "Activity records",
            "status": "Present in gateway" if activity["total"] else "Needs evidence",
            "evidence": f"{activity['total']} stored actions. Local SQLite records are mutable; retention and tamper protection are not verified.",
        },
        {
            "name": "Organisation-wide safeguards",
            "status": "Needs evidence",
            "evidence": "Legal basis, contracts, staff training, retention, encryption, incident response and real deployment controls are outside these checks.",
        },
    ]
    return {
        "findings": findings,
        "controls": controls,
        "activity": activity,
        "recent_evidence": latest,
    }
