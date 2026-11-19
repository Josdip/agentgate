import pytest

from agentgate.cloud import CloudInventoryError, bedrock_agents


def test_bedrock_reads_only_inventory_and_discards_description(monkeypatch):
    calls = []

    def aws(command, region, profile):
        calls.append((command, region, profile))
        if command[0] == "sts":
            return {"Account": "123456789012"}
        return {
            "agentSummaries": [
                {
                    "agentId": "ABCDEF1234",
                    "agentName": "Example",
                    "agentStatus": "PREPARED",
                    "description": "do not store",
                }
            ]
        }

    monkeypatch.setattr("agentgate.cloud.aws_json", aws)
    assert bedrock_agents("us-east-1", "inventory") == (
        "123456789012",
        [("ABCDEF1234", "Example", "PREPARED")],
    )
    assert calls == [
        (["sts", "get-caller-identity"], "us-east-1", "inventory"),
        (["bedrock-agent", "list-agents", "--max-items", "1000"], "us-east-1", "inventory"),
    ]


def test_bedrock_rejects_partial_inventory(monkeypatch):
    def aws(command, region, profile):
        return (
            {"Account": "123456789012"}
            if command[0] == "sts"
            else {"agentSummaries": [], "NextToken": "another page"}
        )

    monkeypatch.setattr("agentgate.cloud.aws_json", aws)
    with pytest.raises(CloudInventoryError, match="scan limit"):
        bedrock_agents("us-east-1", "")
