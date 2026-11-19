# 002. Govern an unmodified local Sonar runtime

Discover running Sonar from its process and loopback listener. Enrollment is a
reviewer action that starts a dedicated instance of the original application
inside Bubblewrap. Preserve the original process and its database. Mount only
the stock source and template, the managed session state, and the broker
credential. Seed the managed session with SQLite’s online backup so it can
retain committed chats and context while the original process stays open. The virtual project directory has no backing access to the real
protected project.

The launcher installs a process-local adapter at Sonar's tool dispatch point.
It submits bounded reads and writes to AgentGate and returns the final tool
result. AgentGate is the only review control for that process. Original source
files and standalone behavior stay intact. Disable unmanaged capabilities in
the managed process and return a generic failure for blocked operations so the
model can continue with independent work.

Only AgentGate's executor opens the protected project. It checks a fresh
authorization and the exact payload before claiming execution. The current
prototype relies on the host operator and shares the host network. Resource
permissions tied to a separate executor identity are the production boundary
for untrusted host processes.
