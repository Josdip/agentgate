"""Pure, deterministic policy evaluation; no caller-supplied identity."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


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


@dataclass(frozen=True)
class Decision:
    outcome: str
    rule: str
    reason: str
    risk: str


SCHEMAS = {"documents.read": DocumentArgs, "refunds.create": RefundArgs, "messages.send": SendArgs}
DOCUMENTS = {
    "refund-policy": "Refunds over $100 require human approval. All refunds are simulated.",
    "support-handbook": "Use approved support channels. Never disclose internal records externally.",
}


def evaluate(call: ToolCall) -> Decision:
    if call.tool not in SCHEMAS:
        return Decision("denied", "tool.allowlist", "Tool is not registered.", "high")
    # Validate even denied requests; schema errors must never reach a tool executor.
    SCHEMAS[call.tool].model_validate(call.arguments)
    if call.tool == "documents.read" and call.arguments["document_id"] not in DOCUMENTS:
        return Decision(
            "denied", "documents.scope", "Document is outside support-agent scope.", "high"
        )
    if call.tool == "messages.send" and call.arguments["destination"] != "support-inbox":
        return Decision("denied", "messages.destination", "Destination is not approved.", "high")
    if call.tool == "refunds.create" and call.arguments["amount_cents"] > 10_000:
        return Decision(
            "pending", "refunds.approval", "Refund exceeds $100; review required.", "medium"
        )
    return Decision("allowed", "tool.scoped", "Action satisfies support-agent policy.", "low")


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
    raise ValueError("Unregistered tool")
