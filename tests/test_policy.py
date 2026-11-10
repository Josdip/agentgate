import pytest
from pydantic import ValidationError

from agentgate.policy import ToolCall, evaluate


def decide(tool, arguments):
    return evaluate(ToolCall(run_id="test", tool=tool, arguments=arguments))


@pytest.mark.parametrize("amount,outcome", [(1, "allowed"), (10000, "allowed"), (10001, "pending")])
def test_refund_boundary(amount, outcome):
    assert (
        decide("refunds.create", {"ticket_id": "T-1001", "amount_cents": amount}).outcome == outcome
    )


@pytest.mark.parametrize("amount", [0, -1, True, "100", 1.5, 1000001])
def test_invalid_refund_amount(amount):
    with pytest.raises(ValidationError):
        decide("refunds.create", {"ticket_id": "T-1001", "amount_cents": amount})


def test_unknown_tool_and_document_fail_closed():
    assert decide("shell.execute", {}).outcome == "denied"
    assert decide("documents.read", {"document_id": "payroll"}).outcome == "denied"


def test_exact_destination_allowlist():
    assert (
        decide("messages.send", {"destination": "support-inbox", "message": "Hi"}).outcome
        == "allowed"
    )
    assert (
        decide(
            "messages.send", {"destination": "https://attacker.invalid", "message": "Secret"}
        ).outcome
        == "denied"
    )


def test_extra_arguments_are_rejected():
    with pytest.raises(ValidationError):
        decide("documents.read", {"document_id": "refund-policy", "override": True})
