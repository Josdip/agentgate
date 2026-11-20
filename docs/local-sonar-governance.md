# Discover and enroll Sonar

Start your existing Sonar on this Linux computer. If it is already running,
leave it open. From a fresh AgentGate checkout, run:

```bash
./start-local
```

The launcher creates the Python 3.12 environment and installs pinned
dependencies on first use. Every launch creates a fresh inventory, audit
history, sample project, and reviewer and Sonar tokens in a private directory
under `~/.local/share/agentgate/demo-sessions`. Scan and enroll again on each
launch. Reopening or refreshing the browser while AgentGate is running stays
in that launch's session. The launcher uses port 8001 if
available and prints the address it selected. Downloaded dependencies and the
Ollama model are separate. Sonar needs Ollama and an installed tool-capable model.

If Ubuntu blocks Bubblewrap, the launcher offers to install an AppArmor profile
for `/usr/bin/bwrap`. This one-time step requires an administrator password.
It leaves the system-wide AppArmor restriction enabled. The launcher verifies
the sandbox before opening AgentGate. On hosts without Bubblewrap, install the
distribution's Bubblewrap package before starting. [Ubuntu AppArmor notes](https://documentation.ubuntu.com/release-notes/24.04/)

1. Open the one-use local link printed by the launcher. It signs you in as the
   local reviewer for this tab. If you reload or the link expires, use the
   reviewer token file printed by the launcher.
2. Select **Scan this computer**, **Add Sonar**, then **Add and launch Sonar**.
   Discovery uses the running process and its loopback listener. The default
   standalone Sonar port is 5000. Set `AGENTGATE_SONAR_PORT` for a custom port.
3. Click **Open managed Sonar**. Your existing chats, projects, and saved context
   are included. AgentGate takes a consistent SQLite snapshot with Sonar
   running. Your original database stays untouched. Standalone and managed
   chats are separate after enrollment, and restarting the managed session
   preserves its new history.
4. Enable tools and project file access in managed Sonar. Ask it to create
   `example.txt` and independently read `welcome.txt`. Writes default to
   **Block**. Reads default to **Require review**. Approve the read in
   **Activity & decisions** and verify that it succeeds and the write stays
   blocked. Change policies in **Rules**.

Stopping AgentGate stops its managed Sonar session. It leaves standalone
Sonar open. Previous demo files remain on disk. Set `AGENTGATE_HOME` to
choose the parent directory for new demos. For persistent AgentGate state across
restarts, run `.venv/bin/python -m agentgate` after sandbox setup. The
runtime detects Sonar's source and chat database from the local process.
Set `AGENTGATE_SONAR_SOURCE` to restrict discovery to a specific checkout.

## Enforcement boundaries

The launcher imports the original Sonar files read-only into Bubblewrap and
installs an AgentGate-owned runtime adapter. The protected project is absent
from the managed process's filesystem. The gateway's executor alone opens the
real directory. Managed Sonar delegates bounded project file reads and writes
to AgentGate, which is its only review control for these actions. Existing Sonar
source and standalone review stay in place. Shell, desktop, GitHub, web search,
and retrieval are disabled in the managed process.

Use a disposable project with no secrets. The sandbox shares the host network
for local Ollama and the broker. Host administrators and standalone
applications running as the desktop user can act outside the sandbox.
Browser and cloud inventory enrollment are available as a preview. Other operating systems are outside this release.

AgentGate stores request metadata and a fingerprint. Proposed content and read
results remain outside its activity database. Approval binds the exact payload
and each request gets one execution claim. A process failure after the claim
can leave a missing receipt. Inspect the target before retrying that action.
