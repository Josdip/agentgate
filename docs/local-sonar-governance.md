# Discover and enroll original Sonar

Use the original Sonar checkout with its stock Python files and browser
interface. AgentGate discovers it using the process and listening socket on
this Linux computer. Discovery creates an inventory candidate. **Add Sonar**
opens an enrollment confirmation. Confirming launches a separate isolated
Sonar instance with its own chat database. The original standalone process
stays open and keeps its existing review flow and chat history.

## Local setup

AgentGate needs Python 3.12, its pinned virtual environment, and Bubblewrap with
user namespaces allowed for the launching process. Sonar needs a local
tool-capable Ollama model. On Ubuntu 24.04, AppArmor can reject Bubblewrap with
a UID-map error. AgentGate reports the launcher log in that case. Use a host
profile that permits Bubblewrap, such as the Codex execution profile used
for local verification.

Start normal Sonar in its source directory, if it is not already running:

```bash
cd ~/homelab/sonar
.venv/bin/python sonar.py
```

In a second terminal, from the AgentGate discovery checkout:

```bash
umask 077
demo=$(mktemp -d)
mkdir "$demo/project"
printf '%s\n' 'Hello from the protected project.' > "$demo/project/welcome.txt"
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$demo/sonar-token"
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$demo/reviewer-token"

cat "$demo/reviewer-token"
AGENTGATE_PROJECT="$demo/project" \
AGENTGATE_DB="$demo/discovery.sqlite3" \
AGENTGATE_SONAR_TOKEN_FILE="$demo/sonar-token" \
AGENTGATE_REVIEWER_TOKEN_FILE="$demo/reviewer-token" \
  .venv/bin/python -m agentgate
```

The defaults are standalone Sonar on port 5000, AgentGate on port 8001, and
managed Sonar on port 5002. Override them with `AGENTGATE_SONAR_PORT`,
`AGENTGATE_PORT`, and `AGENTGATE_MANAGED_SONAR_PORT`. The default Sonar source is
`~/homelab/sonar`, configurable with `AGENTGATE_SONAR_SOURCE`.

## Walk through discovery and enforcement

1. Connect to [AgentGate](http://127.0.0.1:8001/agents) with the local reviewer
   token. Select **Scan this computer**. Select **Add Sonar** and confirm.
2. Open **Open managed Sonar** from its inventory row. Start a chat with a
   tool-capable local model and enable tools and project file access.
3. Ask Sonar to create `example.txt`, then independently read `welcome.txt`
   even if the write is blocked. Writes start at **Block**. Reads start at
   **Require review**. Approve the read in AgentGate’s Activity page.
4. Sonar receives an ordinary blocked result for the write and the file
   contents for the read. AgentGate records each decision and the read receipt.
   The dashboard uses the original theme toggle, navigation, and layout styles.

Stopping the AgentGate process also stops the managed Sonar instance. The
standalone instance stays open.

## Enforcement boundaries

The launcher imports the original Sonar files read-only into Bubblewrap and
installs the AgentGate-owned adapter in memory. The protected project is absent
from that process's filesystem. The gateway's executor alone opens the real
directory. The adapter bypasses Sonar's built-in review inside the managed
process. The standalone process still uses the built-in review. Tool results
provide a generic permission error on denial.

Managed Sonar offers bounded project file reads and writes. It disables shell,
desktop, GitHub, web search, and retrieval in the managed process. Coverage
applies to that process and the protected project path. Use a disposable project
with no secrets. The sandbox shares the host network for local Ollama and the
broker. Host administrators and the standalone application running as your
desktop user can act outside the sandbox. A business deployment would give the
executor an exclusive OS identity and protect the target resource with OS
permissions and network controls.

AgentGate stores request metadata and a fingerprint. Proposed content and read
results remain outside its activity database. Approval binds the exact payload,
rules changes withdraw pending authorizations, and a request gets one execution
claim. A process failure after the claim can leave a missing receipt. Inspect the
target before retrying that action. Sonar uses model reasoning to decide which
later steps can proceed after a denial.
