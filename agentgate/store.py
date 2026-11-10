"""SQLite storage; approval and simulated execution share one transaction."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .policy import SCHEMAS, ToolCall, evaluate, execute


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, agent_id TEXT NOT NULL,
                run_id TEXT NOT NULL, tool TEXT NOT NULL, arguments TEXT NOT NULL,
                outcome TEXT NOT NULL, rule TEXT NOT NULL, reason TEXT NOT NULL,
                risk TEXT NOT NULL, result TEXT, reviewed_at TEXT, reviewer_id TEXT)""")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        item = dict(row)
        item["arguments"] = json.loads(item["arguments"])
        item["result"] = json.loads(item["result"]) if item["result"] else None
        return item

    def submit(self, call: ToolCall):
        decision = evaluate(call)
        action_id = str(uuid4())
        # Do not persist message bodies; governance metadata is sufficient for the demo.
        metadata = (
            dict(call.arguments)
            if call.tool in SCHEMAS
            else {"omitted": "Unregistered tool arguments are not stored."}
        )
        if "message" in metadata:
            metadata["message"] = "[REDACTED]"
        with self.connection() as db:
            db.execute(
                """INSERT INTO actions
                (id,created_at,agent_id,run_id,tool,arguments,outcome,rule,reason,risk)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    action_id,
                    datetime.now(UTC).isoformat(),
                    "support-agent",
                    call.run_id,
                    call.tool,
                    json.dumps(metadata),
                    decision.outcome,
                    decision.rule,
                    decision.reason,
                    decision.risk,
                ),
            )
            if decision.outcome == "allowed":
                result = execute(call.tool, call.arguments)
                db.execute(
                    "UPDATE actions SET outcome='executed',result=? WHERE id=?",
                    (json.dumps(result), action_id),
                )
            return self.decode(
                db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            )

    def list(self):
        with self.connection() as db:
            return [
                self.decode(row)
                for row in db.execute("SELECT * FROM actions ORDER BY created_at DESC LIMIT 200")
            ]

    def review(self, action_id: str, approve: bool):
        with self.connection() as db:
            # Serialize concurrent reviewers before reading the pending state.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if row is None:
                raise KeyError(action_id)
            if row["outcome"] != "pending":
                raise ValueError("Only pending actions can be reviewed; decisions are one-time.")
            result = execute(row["tool"], json.loads(row["arguments"])) if approve else None
            db.execute(
                """UPDATE actions SET outcome=?,result=?,reviewed_at=?,reviewer_id=?
                WHERE id=?""",
                (
                    "executed" if approve else "rejected",
                    json.dumps(result) if result else None,
                    datetime.now(UTC).isoformat(),
                    "local-reviewer",
                    action_id,
                ),
            )
            return self.decode(
                db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            )
