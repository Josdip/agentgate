.PHONY: install run demo check
install:
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
run:
	.venv/bin/python -m agentgate
demo:
	.venv/bin/python examples/demo.py
check:
	.venv/bin/ruff check agentgate tests examples
	.venv/bin/ruff format --check agentgate tests examples
	.venv/bin/pytest -q
