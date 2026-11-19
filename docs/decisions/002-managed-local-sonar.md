# 002. Give the gateway authority over managed file actions

Integrate at Sonar's tool dispatch boundary. Managed Sonar submits a typed
proposal over loopback and waits for AgentGate when human approval is required.
Ordinary Sonar keeps its existing review workflow. The managed runner delegates
file operations to AgentGate's executor and does not provide the model with
parallel shell, browser, repository, or retrieval access.

Use a distinct reviewer token and Sonar token. Discovery checks a known
loopback endpoint, and a fresh nonce paired with an HMAC proves possession
of the Sonar token. An unsigned assertion is discovery evidence only.

Persist only proposal metadata and a fingerprint. At execution, verify the
same payload, valid authorization, current rule revision, and a fresh claim.
Commit the claim before touching the filesystem. This prevents duplicate
execution. A crash between a file write and its receipt leaves an uncertain
record for the operator to investigate. File writes replace a temporary file
in the target directory atomically.

The enforcement boundary is the integrated model tool path. Separate OS
identities and exclusive executor filesystem permissions are required to
enforce against arbitrary code running as the agent host's user.
