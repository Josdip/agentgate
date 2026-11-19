"""Read-only discovery of agents in an authorized AWS Bedrock account."""

import json
import re
import subprocess


class CloudInventoryError(RuntimeError):
    """Cloud inventory is unavailable or incomplete."""


def aws_json(command, region, profile):
    args = ["aws", *command, "--region", region, "--output", "json", "--no-cli-pager"]
    if profile:
        args.extend(["--profile", profile])
    try:
        result = subprocess.run(args, capture_output=True, check=True, timeout=40)
        return json.loads(result.stdout)
    except FileNotFoundError as exc:
        raise CloudInventoryError(
            "Install AWS CLI v2 on the AgentGate host to scan Bedrock."
        ) from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as exc:
        raise CloudInventoryError(
            "AWS scan failed. Check the AWS CLI session, region, and read permissions."
        ) from exc


def bedrock_agents(region, profile):
    identity = aws_json(["sts", "get-caller-identity"], region, profile)
    account = identity.get("Account") if isinstance(identity, dict) else None
    if not isinstance(account, str) or not re.fullmatch(r"[0-9]{12}", account):
        raise CloudInventoryError("AWS returned an invalid account identity.")

    document = aws_json(["bedrock-agent", "list-agents", "--max-items", "1000"], region, profile)
    if not isinstance(document, dict) or not isinstance(document.get("agentSummaries"), list):
        raise CloudInventoryError("Bedrock returned an invalid inventory response.")
    if document.get("NextToken") or document.get("nextToken"):
        raise CloudInventoryError(
            "This account and region exceed the connector’s 1,000-agent scan limit."
        )

    agents = []
    for item in document["agentSummaries"]:
        if not isinstance(item, dict):
            raise CloudInventoryError("Bedrock returned an invalid agent record.")
        identifier, name, status = (
            item.get(field) for field in ("agentId", "agentName", "agentStatus")
        )
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[a-zA-Z0-9]{10}", identifier)
            or not isinstance(name, str)
            or not 1 <= len(name) <= 100
            or not isinstance(status, str)
            or not re.fullmatch(r"[A-Z_]{1,40}", status)
        ):
            raise CloudInventoryError("Bedrock returned an invalid agent record.")
        agents.append((identifier, name, status))
    return account, agents
