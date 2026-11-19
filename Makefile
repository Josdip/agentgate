.PHONY: install run demo check check-interface
install:
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
run:
	.venv/bin/python -m agentgate
demo: run
check:
	.venv/bin/ruff check agentgate tests examples
	.venv/bin/ruff format --check agentgate tests examples
	.venv/bin/pytest -q

# Optional local interface regressions (Node.js 18+; no npm dependencies).
check-interface:
	node --check agentgate/static/managed.js
	node --test tests/interface.test.cjs
