# AgentGate

AgentGate inventories local AI runtimes and governs supported tool actions.
This release starts with an empty inventory and integrates with Sonar, a local
Ollama agent. Discovery distinguishes a compatible Sonar endpoint from a Sonar
instance that can prove its AgentGate pairing.

In managed mode Sonar proposes project file reads and writes. AgentGate records
the applicable rule and performs authorized actions through its file executor.
An operator can allow, block, or require review per tool. Activity distinguishes
a proposal, its authorization, and the outcome of execution.

- [Run the local Sonar integration](docs/local-sonar-governance.md)
- [Design decision and trust boundary](docs/decisions/002-managed-local-sonar.md)
- [Contributing](CONTRIBUTING.md)

Python 3.12+ · FastAPI · SQLite · browser-native JavaScript

```sh
make check
make check-interface
```

The earlier synthetic applications remain in source for compatibility tests.
The default launcher serves the new workspace with authenticated reviewer access.
