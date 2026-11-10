"""Server-owned demo identities and their effective access scopes."""

AGENTS = {
    "support-agent": {
        "name": "Support agent",
        "description": "Helps customers and handles refund requests.",
        "location": "Cloud",
        "owner": "Customer service",
        "tools": {
            "documents.read": ["refund-policy", "support-handbook"],
            "refunds.create": ["T-1001", "T-1002"],
            "messages.send": ["support-inbox"],
        },
    },
    "sales-agent": {
        "name": "Sales assistant",
        "description": "Reads approved leads and prepares sales outreach.",
        "location": "Browser",
        "owner": "Sales",
        "tools": {"crm.read": ["LEAD-1001", "LEAD-1002"], "messages.send": ["sales-inbox"]},
    },
    "finance-agent": {
        "name": "Finance assistant",
        "description": "Checks invoices and requests supplier payments.",
        "location": "Endpoint",
        "owner": "Finance",
        "tools": {"invoices.read": ["INV-1001", "INV-1002"], "payments.create": ["V-1001"]},
    },
}
