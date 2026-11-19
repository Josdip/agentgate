# Browser and cloud discovery preview

These connectors add inventory entries. Enforcement and review currently
cover the managed Sonar file tools. A browser report or Bedrock catalog entry
does not grant permission to inspect conversations or control cloud tools.

## ChatGPT in Chrome

1. Open AgentGate and connect as reviewer. On **Agents**, open **ChatGPT in
   Chrome** and generate a discovery code.
2. In Chrome, visit `chrome://extensions`, turn on **Developer mode**, and
   use **Load unpacked** to select this repository's `connectors/chrome` folder.
3. Open ChatGPT in Chrome and click the **AgentGate Browser Discovery**
   extension. Enter the local AgentGate address and the discovery code.
   Select **Report active tab**.
4. AgentGate lists **ChatGPT** as a browser discovery. The code is usable once
   and expires after 10 minutes. The extension checks the active tab only
   after you click it. It sends a service label without the full URL,
   conversations, cookies, credentials, or browser history.

This is an operator-initiated report from a browser with the connector
installed. It does not independently verify account ownership or whether a
specific hosted agent is active.
[Chrome activeTab documentation](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab)

## AWS Bedrock Agents

1. Install AWS CLI v2 on the computer running AgentGate. Sign in with your
   usual organization-authorized AWS CLI profile. Allow `bedrock:ListAgents`
   in the target account and region.
2. On AgentGate’s **Agents** page, open **AWS Bedrock Agents**. Enter the
   region and optionally the CLI profile name.
3. Select **Scan Bedrock Agents**. AgentGate uses the CLI identity to identify
   the account and refreshes that account and region's inventory. The previous
   inventory remains intact if the scan fails. The current limit is 1,000
   Bedrock Agents per account and region.

AgentGate stores IDs, names, provider statuses, AWS account and region, and
the discovery timestamp. It uses the existing AWS CLI session and does not
take AWS credentials in its browser form.
[AWS CLI list-agents reference](https://docs.aws.amazon.com/cli/latest/reference/bedrock-agent/list-agents.html)
