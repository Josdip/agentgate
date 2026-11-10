"""Pure rule evaluation. Runtime passes stored rules; defaults support seed examples/tests."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .registry import AGENTS


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ToolCall(StrictModel):
    run_id: str = Field(min_length=1, max_length=100)
    tool: str = Field(min_length=1, max_length=80)
    arguments: dict


class DocumentArgs(StrictModel):
    document_id: str = Field(min_length=1, max_length=80)


class RefundArgs(StrictModel):
    ticket_id: Literal["T-1001", "T-1002"]
    amount_cents: StrictInt = Field(gt=0, le=1_000_000)


class SendArgs(StrictModel):
    destination: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)


class LeadArgs(StrictModel):
    lead_id: str = Field(min_length=1, max_length=80)


class InvoiceArgs(StrictModel):
    invoice_id: str = Field(min_length=1, max_length=80)


class PaymentArgs(StrictModel):
    vendor_id: str = Field(min_length=1, max_length=80)
    amount_cents: StrictInt = Field(gt=0, le=1_000_000)


@dataclass(frozen=True)
class Decision:
    outcome: str
    rule: str
    reason: str
    risk: str
    matched_rule_id: str | None = None


SCHEMAS = {
    "documents.read": DocumentArgs,
    "refunds.create": RefundArgs,
    "messages.send": SendArgs,
    "crm.read": LeadArgs,
    "invoices.read": InvoiceArgs,
    "payments.create": PaymentArgs,
}
DOCUMENTS = {
    "refund-policy": "Refund requests follow this agent’s current gateway rules. All refunds are simulated.",
    "support-handbook": "Use approved support channels. Never disclose internal records externally.",
}


REFUND_LIMIT_CENTS = 10_000
APPROVED_DESTINATIONS = ("support-inbox",)


PAYMENT_LIMIT_CENTS = 50_000
TOOL_LABELS = {
    "documents.read": "Read approved support documents",
    "refunds.create": "Issue customer refunds",
    "messages.send": "Send messages to approved inboxes",
    "crm.read": "Read approved sales leads",
    "invoices.read": "Read approved invoices",
    "payments.create": "Pay approved suppliers",
}
SCOPE_FIELDS = {
    "documents.read": "document_id",
    "refunds.create": "ticket_id",
    "messages.send": "destination",
    "crm.read": "lead_id",
    "invoices.read": "invoice_id",
    "payments.create": "vendor_id",
}


def default_rules(agent_id):
    return [
        {
            "id": "default-" + tool.replace(".", "-"),
            "name": TOOL_LABELS[tool],
            "tool": tool,
            "decision": "allow",
            "scope": list(scope),
            "approval_threshold_cents": (
                REFUND_LIMIT_CENTS
                if tool == "refunds.create"
                else PAYMENT_LIMIT_CENTS
                if tool == "payments.create"
                else None
            ),
        }
        for tool, scope in AGENTS[agent_id]["tools"].items()
    ]


def tool_permissions(agent_id="support-agent", rules=None):
    result = []
    for rule in sorted(
        default_rules(agent_id) if rules is None else rules, key=lambda item: item["tool"]
    ):
        entry = {
            "tool": rule["tool"],
            "permission": TOOL_LABELS[rule["tool"]],
            "scope": rule["scope"],
            "rule_id": rule["id"],
            "decision": rule["decision"],
            "approval": {
                "allow": "Not required within scope",
                "deny": "Blocked for this agent",
                "review": "Human approval required for every request",
            }[rule["decision"]],
        }
        if rule["decision"] == "allow" and rule["approval_threshold_cents"] is not None:
            limit = rule["approval_threshold_cents"]
            entry.update(
                automatic_limit_cents=limit,
                approval=f"Human approval above ${limit / 100:,.2f} per request",
            )
        result.append(entry)
    return result


def evaluate(call: ToolCall, agent_id="support-agent", rules=None) -> Decision:
    if agent_id not in AGENTS:
        return Decision("denied", "agent.unknown", "Agent identity is not registered.", "high")
    if call.tool not in SCHEMAS:
        return Decision("denied", "tool.allowlist", "Tool is not registered.", "high")
    SCHEMAS[call.tool].model_validate(call.arguments)
    configured = default_rules(agent_id) if rules is None else rules
    rule = next((item for item in configured if item["tool"] == call.tool), None)
    if rule is None:
        return Decision(
            "denied", "agent.tool_scope", "No rule grants this agent access to this tool.", "high"
        )
    matched = rule["id"]
    if rule["decision"] == "deny":
        return Decision(
            "denied", "rule.deny", "This tool is blocked by the agent’s rule.", "high", matched
        )
    if call.arguments[SCOPE_FIELDS[call.tool]] not in rule["scope"]:
        classification = {
            "documents.read": "documents.scope",
            "messages.send": "messages.destination",
        }.get(call.tool, "resource.scope")
        return Decision(
            "denied",
            classification,
            "The requested resource or destination is outside this agent’s approved access.",
            "high",
            matched,
        )
    if rule["decision"] == "review":
        return Decision(
            "pending",
            "rule.review",
            "The agent’s rule requires a human decision for every request to this tool.",
            "medium",
            matched,
        )
    limit = rule["approval_threshold_cents"]
    if limit is not None and call.arguments["amount_cents"] > limit:
        classification = (
            "refunds.approval" if call.tool == "refunds.create" else "payments.approval"
        )
        return Decision(
            "pending",
            classification,
            f"Amount exceeds ${limit / 100:,.2f}; human approval required.",
            "medium",
            matched,
        )
    return Decision(
        "allowed",
        "tool.scoped",
        "Action is within this agent’s approved permissions.",
        "low",
        matched,
    )


def execute(tool: str, arguments: dict) -> dict:
    """Synthetic effects only. Never performs network calls or moves money."""
    if tool == "documents.read":
        return {"content": DOCUMENTS[arguments["document_id"]], "simulated": True}
    if tool == "refunds.create":
        return {
            "ticket_id": arguments["ticket_id"],
            "amount_cents": arguments["amount_cents"],
            "simulated": True,
        }
    if tool == "messages.send":
        return {"destination": arguments["destination"], "delivered": False, "simulated": True}
    if tool == "crm.read":
        return {"lead_id": arguments["lead_id"], "company": "Example customer", "simulated": True}
    if tool == "invoices.read":
        return {"invoice_id": arguments["invoice_id"], "vendor_id": "V-1001", "simulated": True}
    if tool == "payments.create":
        return {**arguments, "simulated": True}
    raise ValueError("Unregistered tool")
