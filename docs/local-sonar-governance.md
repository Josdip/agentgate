# Discover and govern Sonar on this computer

AgentGate checks a configured loopback Sonar endpoint when you select
**Scan this computer**. Sonar running this integration code identifies itself
in standalone mode. In managed mode, Sonar uses the pairing token to answer a
fresh challenge. The inventory distinguishes **Discovered**, **Managed**, and
**Unreachable at last scan**. The workspace starts empty. Browser and cloud
connectors are outside this release.

## Start the two services

Use the AgentGate discovery branch and Sonar's `codex/sonar-agentgate-managed`
branch. Install the pinned AgentGate environment if this is a fresh checkout.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install --no-deps --no-build-isolation -e .
```

Confirm `ollama list` works and a local tool-capable chat model is installed.
From the AgentGate checkout, run in one Bash terminal:

```bash
umask 077
demo=$(mktemp -d)
mkdir "$demo/project"
printf '%s\n' 'AgentGate is governing this project.' > "$demo/project/welcome.txt"
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$demo/sonar-token"
python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > "$demo/reviewer-token"

AGENTGATE_PROJECT="$demo/project" \
AGENTGATE_DB="$demo/discovery.sqlite3" \
AGENTGATE_SONAR_TOKEN_FILE="$demo/sonar-token" \
AGENTGATE_REVIEWER_TOKEN_FILE="$demo/reviewer-token" \
AGENTGATE_SONAR_PORT=5001 \
  .venv/bin/python -m agentgate &
gateway=$!

sonar="$HOME/homelab/sonar"
(
  cd "$sonar"
  exec env SONAR_PORT=5001 SONAR_DB="$demo/sonar.sqlite3" \
    SONAR_AGENTGATE_URL=http://127.0.0.1:8001 \
    SONAR_AGENTGATE_TOKEN_FILE="$demo/sonar-token" \
    .venv/bin/python sonar.py
) &
sonar_pid=$!
```

The dedicated project and chat database keep the demo separate from your usual
Sonar workspace. Ports 8001 and 5001 let this run beside the original demos.
Both listeners use loopback. Use `cat "$demo/reviewer-token"` locally to copy
the reviewer token into [AgentGate](http://127.0.0.1:8001/agents).

## Walk through a rule

1. In AgentGate, connect and select **Scan this computer**. Sonar should show
   **Managed**. Reads begin at **Require review** and writes at **Block**.
2. Open [Sonar](http://127.0.0.1:5001), create a chat, select a tool-capable
   local model, enable tools and project file access, and ask it to read
   `welcome.txt` using `read_file`.
3. In AgentGate, approve the pending action. Sonar receives the read result.
   AgentGate shows authorization and execution as separate states.
4. Ask Sonar to create `note.txt` with a short line. The default write rule
   blocks it. Change the rule to **Require review**, ask again, and approve
   the new request to write the file. A rule change withdraws outstanding
   authorization under the previous revision.

Stop these services with `kill "$sonar_pid" "$gateway"`. For standalone Sonar,
start it without either `SONAR_AGENTGATE_*` setting. Its ordinary review
remains available.

## Boundaries

The executor pins a dedicated project directory and accepts only bounded text
reads and writes on relative paths. It rejects private paths, symbolic links,
and multiply linked files. Keep this directory free of credentials, sensitive
files, and shared or untrusted writers. AgentGate stores the target, action,
policy decision, proposal fingerprint, and outcome. It does not persist the
proposed write content or file read result. A write review shows the target,
byte count, and fingerprint. It cannot show a content diff in this release.

Pending and authorized proposals expire after five minutes. Sonar holds the
payload while the chat is active. Restarting Sonar requires a fresh proposal.
A failed response never triggers local execution or an automatic write retry.
If AgentGate stops after it claims execution, the activity can show a missing
receipt. Inspect the project before submitting a replacement.

Managed Sonar exposes only the two supported file tools. Terminal, desktop,
GitHub, web search, and retrieval are disabled in that mode. Normal chat
inference continues through Ollama. This local prototype trusts both service
processes and the OS user running them. The model has no unrestricted file
tool, but an administrator or arbitrary host code running with that user's
permissions can modify the project outside AgentGate. A business deployment
would put the executor under a separate OS identity and give that identity
exclusive access to managed resources.
