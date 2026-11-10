"""SQLite storage; approval and simulated execution share one transaction."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .policy import SCHEMAS, ToolCall, evaluate, execute, tool_permissions
from .profile import ProfileUpdate


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

            db.execute("""CREATE TABLE IF NOT EXISTS agent_profiles (
                agent_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL, metadata TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS profile_history (
                agent_id TEXT NOT NULL, revision INTEGER NOT NULL, changed_at TEXT NOT NULL,
                changed_by TEXT NOT NULL, metadata TEXT NOT NULL,
                PRIMARY KEY (agent_id, revision))""")
            now = datetime.now(UTC).isoformat()
            metadata = json.dumps(
                {
                    "display_name": "Support agent",
                    "description": "Synthetic customer-support agent governed by AgentGate.",
                    "model_connections": [],
                }
            )
            cursor = db.execute(
                "INSERT OR IGNORE INTO agent_profiles VALUES (?,?,?,?,?)",
                ("support-agent", now, now, 1, metadata),
            )
            if cursor.rowcount:
                db.execute(
                    "INSERT INTO profile_history VALUES (?,?,?,?,?)",
                    ("support-agent", 1, now, "system", metadata),
                )

    def profile(self):
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM agent_profiles WHERE agent_id='support-agent'"
            ).fetchone()
            profile = dict(row)
            profile.update(json.loads(profile.pop("metadata")))
            for connection in profile["model_connections"]:
                connection["verification"] = "unverified"
            profile["tools"] = tool_permissions()
            profile["permissions"] = {
                "identity_source": "server-owned agent credential",
                "unknown_tools": "denied",
                "can_review_actions": False,
                "policy_source": "gateway-enforced policy v1",
                "execution_mode": "synthetic",
            }
            profile["activity"] = dict(
                db.execute("""SELECT COUNT(*) AS total_actions,
                COALESCE(SUM(outcome='denied'),0) AS denied,
                COALESCE(SUM(outcome='pending'),0) AS pending,
                COALESCE(SUM(outcome='executed'),0) AS executed,
                MIN(created_at) AS first_seen, MAX(created_at) AS last_seen
                FROM actions WHERE agent_id='support-agent'""").fetchone()
            )
            profile["history"] = [
                {**dict(item), "metadata": json.loads(item["metadata"])}
                for item in db.execute("""SELECT revision,changed_at,changed_by,metadata
                    FROM profile_history WHERE agent_id='support-agent'
                    ORDER BY revision DESC LIMIT 20""")
            ]
            return profile

    def update_profile(self, update: ProfileUpdate):
        metadata = update.model_dump(exclude={"revision"})
        now = datetime.now(UTC).isoformat()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                """UPDATE agent_profiles SET revision=revision+1,
                updated_at=?,metadata=? WHERE agent_id='support-agent' AND revision=?""",
                (now, json.dumps(metadata), update.revision),
            )
            if not cursor.rowcount:
                raise ValueError("Profile changed; reload before saving again.")
            db.execute(
                "INSERT INTO profile_history VALUES (?,?,?,?,?)",
                ("support-agent", update.revision + 1, now, "local-reviewer", json.dumps(metadata)),
            )
        return self.profile()

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
