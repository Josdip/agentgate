# ADR 001: local-first, deterministic enforcement

Status: accepted

Build the first vertical slice with Python/FastAPI, SQLite, and browser-native HTML/CSS/JavaScript. This keeps setup small and makes core security behavior inspectable without a paid model API, Node build chain, or database server. PostgreSQL and a richer frontend remain later migrations, not prerequisites.

The gateway owns tool execution. Caller-supplied agent names do not establish identity. Tool parameters use strict schemas, unknown tools fail closed, and approvals refer to stored immutable requests.

Use separate agent and reviewer bearer tokens loaded from the environment. These are development credentials, not a substitute for production identity or tenant isolation. The browser keeps the reviewer token in memory only.
