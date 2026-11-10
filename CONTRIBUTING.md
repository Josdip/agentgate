# Contributing

Read the architecture and threat model first. Keep changes focused and include meaningful tests for policy or authorization changes. Never commit credentials, real customer data, generated databases, or virtual environments.

Use descriptive commits such as `feat(policy): deny out-of-scope document access` or `test(approval): reject replayed decisions`. Update documentation with behavior changes. Record material design decisions in `docs/decisions/`.

Run the checks documented in `docs/development.md` before committing. Do not describe planned functionality as implemented.
