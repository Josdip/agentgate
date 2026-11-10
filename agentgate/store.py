"""SQLite storage; approval and simulated execution share one transaction."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .policy import (
    SCHEMAS,
    SCOPE_FIELDS,
    TOOL_LABELS,
    ToolCall,
    default_rules,
    evaluate,
    execute,
    tool_permissions,
)
from .profile import ProfileUpdate
from .registry import AGENTS
from .rules import RuleChange
from .security import CATALOG_VERSION, FRAMEWORKS, ApplicabilityUpdate, assess


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
            for column in ("agent_id", "outcome", "risk"):
                db.execute(f"CREATE INDEX IF NOT EXISTS actions_{column} ON actions({column})")
            db.execute("""CREATE TABLE IF NOT EXISTS compliance_scope (
                agent_id TEXT NOT NULL, framework TEXT NOT NULL, revision INTEGER NOT NULL,
                applicability TEXT NOT NULL, rationale TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(agent_id, framework))""")
            db.execute("""CREATE TABLE IF NOT EXISTS compliance_scope_history (
                agent_id TEXT NOT NULL, framework TEXT NOT NULL, revision INTEGER NOT NULL,
                applicability TEXT NOT NULL, rationale TEXT NOT NULL, changed_at TEXT NOT NULL,
                changed_by TEXT NOT NULL, PRIMARY KEY(agent_id, framework, revision))""")
            now = datetime.now(UTC).isoformat()
            for agent_id, config in AGENTS.items():
                metadata = json.dumps(
                    {
                        "display_name": config["name"],
                        "description": config["description"],
                        "model_connections": [],
                    }
                )
                cursor = db.execute(
                    "INSERT OR IGNORE INTO agent_profiles VALUES (?,?,?,?,?)",
                    (agent_id, now, now, 1, metadata),
                )
                if cursor.rowcount:
                    db.execute(
                        "INSERT INTO profile_history VALUES (?,?,?,?,?)",
                        (agent_id, 1, now, "system", metadata),
                    )

        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(actions)")}
            for name, kind in (("policy_revision", "INTEGER"), ("matched_rule_id", "TEXT")):
                if name not in columns:
                    db.execute(f"ALTER TABLE actions ADD COLUMN {name} {kind}")
            db.execute("""CREATE TABLE IF NOT EXISTS agent_policies (
                agent_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS policy_rules (
                agent_id TEXT NOT NULL, rule_id TEXT NOT NULL, tool TEXT NOT NULL, spec TEXT NOT NULL,
                PRIMARY KEY(agent_id,rule_id), UNIQUE(agent_id,tool))""")
            db.execute("""CREATE TABLE IF NOT EXISTS policy_history (
                agent_id TEXT NOT NULL, revision INTEGER NOT NULL, changed_at TEXT NOT NULL,
                changed_by TEXT NOT NULL, operation TEXT NOT NULL, rule_id TEXT, snapshot TEXT NOT NULL,
                PRIMARY KEY(agent_id,revision))""")
            for agent_id in AGENTS:
                cursor = db.execute(
                    "INSERT OR IGNORE INTO agent_policies VALUES (?,1,?)", (agent_id, now)
                )
                if cursor.rowcount:
                    for rule in default_rules(agent_id):
                        spec = {key: value for key, value in rule.items() if key != "id"}
                        db.execute(
                            "INSERT INTO policy_rules VALUES (?,?,?,?)",
                            (agent_id, rule["id"], rule["tool"], json.dumps(spec)),
                        )
                    self._policy_history(db, agent_id, "seed", None, "system")

    @staticmethod
    def _policy(db, agent_id):
        row = db.execute("SELECT * FROM agent_policies WHERE agent_id=?", (agent_id,)).fetchone()
        if row is None:
            raise KeyError("Agent not found")
        result = dict(row)
        result["rules"] = [
            {"id": item["rule_id"], **json.loads(item["spec"])}
            for item in db.execute(
                "SELECT * FROM policy_rules WHERE agent_id=? ORDER BY tool", (agent_id,)
            )
        ]
        return result

    def _policy_history(self, db, agent_id, operation, rule_id, actor="local-reviewer"):
        policy = self._policy(db, agent_id)
        db.execute(
            "INSERT INTO policy_history VALUES (?,?,?,?,?,?,?)",
            (
                agent_id,
                policy["revision"],
                policy["updated_at"],
                actor,
                operation,
                rule_id,
                json.dumps(policy["rules"]),
            ),
        )

    def rules(self, agent_id):
        with self.connection() as db:
            db.execute("BEGIN")
            policy = self._policy(db, agent_id)
            policy["history"] = [
                {**dict(row), "snapshot": json.loads(row["snapshot"])}
                for row in db.execute(
                    "SELECT * FROM policy_history WHERE agent_id=? ORDER BY revision DESC LIMIT 20",
                    (agent_id,),
                )
            ]
            policy["catalog"] = [
                {
                    "tool": tool,
                    "label": TOOL_LABELS[tool],
                    "scope_field": SCOPE_FIELDS[tool],
                    "monetary": tool in {"refunds.create", "payments.create"},
                    "suggested_targets": sorted(
                        {
                            target
                            for agent in AGENTS.values()
                            for target in agent["tools"].get(tool, [])
                        }
                    ),
                }
                for tool in SCHEMAS
            ]
            return policy

    def change_rule(self, agent_id, change: RuleChange | None, *, rule_id=None, revision=None):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            policy = self._policy(db, agent_id)
            expected = change.revision if change else revision
            if expected != policy["revision"]:
                raise ValueError("Rules changed. Reload the rules before saving.")
            existing = next((rule for rule in policy["rules"] if rule["id"] == rule_id), None)
            if rule_id is not None and existing is None:
                raise KeyError("Rule not found")
            if change is not None:
                if any(
                    rule["tool"] == change.rule.tool and rule["id"] != rule_id
                    for rule in policy["rules"]
                ):
                    raise ValueError(
                        "This tool already has a rule. Edit or remove that rule first."
                    )
                spec = change.rule.model_dump()
                if rule_id is None:
                    rule_id = str(uuid4())
                    db.execute(
                        "INSERT INTO policy_rules VALUES (?,?,?,?)",
                        (agent_id, rule_id, spec["tool"], json.dumps(spec)),
                    )
                    operation = "add"
                else:
                    db.execute(
                        "UPDATE policy_rules SET tool=?,spec=? WHERE agent_id=? AND rule_id=?",
                        (spec["tool"], json.dumps(spec), agent_id, rule_id),
                    )
                    operation = "edit"
            else:
                db.execute(
                    "DELETE FROM policy_rules WHERE agent_id=? AND rule_id=?", (agent_id, rule_id)
                )
                operation = "delete"
            db.execute(
                "UPDATE agent_policies SET revision=revision+1,updated_at=? WHERE agent_id=?",
                (datetime.now(UTC).isoformat(), agent_id),
            )
            self._policy_history(db, agent_id, operation, rule_id)
        return self.rules(agent_id)

    def profile(self, agent_id="support-agent"):
        if agent_id not in AGENTS:
            raise KeyError(agent_id)
        with self.connection() as db:
            db.execute("BEGIN")
            row = db.execute(
                "SELECT * FROM agent_profiles WHERE agent_id=?", (agent_id,)
            ).fetchone()
            profile = dict(row)
            profile.update(json.loads(profile.pop("metadata")))
            for connection in profile["model_connections"]:
                connection["verification"] = "unverified"
            policy = self._policy(db, agent_id)
            profile["tools"] = tool_permissions(agent_id, policy["rules"])
            profile["policy_revision"] = policy["revision"]
            profile["location"] = AGENTS[agent_id]["location"]
            profile["owner"] = AGENTS[agent_id]["owner"]
            profile["connection_status"] = "simulated demo"
            profile["permissions"] = {
                "identity_source": "server-owned agent credential",
                "unknown_tools": "denied",
                "can_review_actions": False,
                "policy_source": "gateway-enforced stored rules",
                "execution_mode": "synthetic",
            }
            profile["activity"] = dict(
                db.execute(
                    """SELECT COUNT(*) AS total_actions,
                COALESCE(SUM(outcome='denied'),0) AS denied,
                COALESCE(SUM(outcome='pending'),0) AS pending,
                COALESCE(SUM(outcome='executed'),0) AS executed,
                MIN(created_at) AS first_seen, MAX(created_at) AS last_seen
                FROM actions WHERE agent_id=?""",
                    (agent_id,),
                ).fetchone()
            )
            profile["history"] = [
                {**dict(item), "metadata": json.loads(item["metadata"])}
                for item in db.execute(
                    """SELECT revision,changed_at,changed_by,metadata
                    FROM profile_history WHERE agent_id=?
                    ORDER BY revision DESC LIMIT 20""",
                    (agent_id,),
                )
            ]
            return profile

    def update_profile(self, update: ProfileUpdate, agent_id="support-agent"):
        if agent_id not in AGENTS:
            raise KeyError(agent_id)
        metadata = update.model_dump(exclude={"revision"})
        now = datetime.now(UTC).isoformat()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            cursor = db.execute(
                """UPDATE agent_profiles SET revision=revision+1,
                updated_at=?,metadata=? WHERE agent_id=? AND revision=?""",
                (now, json.dumps(metadata), agent_id, update.revision),
            )
            if not cursor.rowcount:
                raise ValueError("Profile changed; reload before saving again.")
            db.execute(
                "INSERT INTO profile_history VALUES (?,?,?,?,?)",
                (agent_id, update.revision + 1, now, "local-reviewer", json.dumps(metadata)),
            )
        return self.profile(agent_id)

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

    def submit(self, call: ToolCall, agent_id="support-agent"):
        if agent_id not in AGENTS:
            raise KeyError(agent_id)
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
            db.execute("BEGIN IMMEDIATE")
            policy = self._policy(db, agent_id)
            decision = evaluate(call, agent_id, policy["rules"])
            db.execute(
                """INSERT INTO actions
                (id,created_at,agent_id,run_id,tool,arguments,outcome,rule,reason,risk,policy_revision,matched_rule_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    action_id,
                    datetime.now(UTC).isoformat(),
                    agent_id,
                    call.run_id,
                    call.tool,
                    json.dumps(metadata),
                    decision.outcome,
                    decision.rule,
                    decision.reason,
                    decision.risk,
                    policy["revision"],
                    decision.matched_rule_id,
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

    def directory(self):
        return [self.profile(agent_id) for agent_id in AGENTS]

    def overview(self):
        with self.connection() as db:
            summary = dict(
                db.execute("""SELECT COUNT(*) AS total,
                COALESCE(SUM(outcome='pending'),0) AS pending,
                COALESCE(SUM(outcome='denied'),0) AS denied,
                COALESCE(SUM(outcome='executed'),0) AS executed
                FROM actions""").fetchone()
            )
            summary["agents"] = len(AGENTS)
            summary["recent"] = [
                self.decode(row)
                for row in db.execute("SELECT * FROM actions ORDER BY rowid DESC LIMIT 3")
            ]
            return summary

    def activity(self, *, agent_id=None, outcome=None, risk=None, search="", before=None, limit=20):
        clauses, values = [], []
        for column, value in (("agent_id", agent_id), ("outcome", outcome), ("risk", risk)):
            if value:
                clauses.append(f"{column}=?")
                values.append(value)
        if search:
            clauses.append(
                "(tool LIKE ? ESCAPE '\\' OR run_id LIKE ? ESCAPE '\\' OR reason LIKE ? ESCAPE '\\')"
            )
            term = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            values.extend([term] * 3)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connection() as db:
            total = db.execute("SELECT COUNT(*) FROM actions" + where, values).fetchone()[0]
            page_clauses = clauses + (["rowid < ?"] if before is not None else [])
            page_values = values + ([before] if before is not None else [])
            page_where = " WHERE " + " AND ".join(page_clauses) if page_clauses else ""
            rows = db.execute(
                "SELECT rowid AS cursor,* FROM actions"
                + page_where
                + " ORDER BY rowid DESC LIMIT ?",
                [*page_values, limit + 1],
            ).fetchall()
            has_more = len(rows) > limit
            items = [self.decode(row) for row in rows[:limit]]
            return {
                "items": items,
                "total": total,
                "next_cursor": items[-1]["cursor"] if has_more else None,
            }

    def security(self, agent_id):
        if agent_id not in AGENTS:
            raise KeyError("Agent not found")
        with self.connection() as db:
            db.execute("BEGIN")
            policy = self._policy(db, agent_id)
            profile = db.execute(
                "SELECT * FROM agent_profiles WHERE agent_id=?", (agent_id,)
            ).fetchone()
            activity = dict(
                db.execute(
                    """SELECT COUNT(*) AS total,
                COALESCE(SUM(outcome='denied'),0) AS denied,
                COALESCE(SUM(outcome='pending'),0) AS pending,
                COALESCE(SUM(outcome='executed'),0) AS executed
                FROM actions WHERE agent_id=?""",
                    (agent_id,),
                ).fetchone()
            )
            latest = [
                dict(row)
                for row in db.execute(
                    """SELECT id,run_id,created_at,tool,outcome,
                rule,policy_revision FROM actions WHERE agent_id=? ORDER BY rowid DESC LIMIT 5""",
                    (agent_id,),
                )
            ]
            frameworks = []
            for key, spec in FRAMEWORKS.items():
                scope = db.execute(
                    "SELECT * FROM compliance_scope WHERE agent_id=? AND framework=?",
                    (agent_id, key),
                ).fetchone()
                declaration = (
                    dict(scope)
                    if scope
                    else {
                        "revision": 0,
                        "applicability": "unknown",
                        "rationale": "",
                        "updated_at": None,
                    }
                )
                frameworks.append(
                    dict(
                        id=key,
                        **spec,
                        **declaration,
                        compliance_status="Not assessed",
                        control_review=(
                            "Review the supporting controls and unresolved evidence before making a compliance decision."
                            if declaration["applicability"] == "applies"
                            else "Confirm scope first. No compliance conclusion has been made."
                        ),
                        supporting_controls=(
                            [
                                "Exact resource boundaries",
                                "Activity records",
                                "Organisation-wide safeguards",
                            ]
                            if key != "eu-ai-act"
                            else [
                                "Human oversight configuration",
                                "Activity records",
                                "Use-case and role classification",
                            ]
                        ),
                        provenance="Reviewer declaration; not independently verified",
                    )
                )
            return dict(
                agent_id=agent_id,
                display_name=json.loads(profile["metadata"])["display_name"],
                owner=AGENTS[agent_id]["owner"],
                policy_revision=policy["revision"],
                profile_revision=profile["revision"],
                catalog_version=CATALOG_VERSION,
                evaluated_at=datetime.now(UTC).isoformat(),
                frameworks=frameworks,
                **assess(policy, json.loads(profile["metadata"]), activity, latest),
            )

    def update_compliance_scope(self, agent_id, framework, update: ApplicabilityUpdate):
        if agent_id not in AGENTS or framework not in FRAMEWORKS:
            raise KeyError("Agent or framework not found")
        if not update.rationale.strip() or len(update.rationale.strip()) < 10:
            raise ValueError("Explain the applicability decision in at least 10 characters")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT revision FROM compliance_scope WHERE agent_id=? AND framework=?",
                (agent_id, framework),
            ).fetchone()
            if update.revision != (row["revision"] if row else 0):
                raise ValueError("Applicability changed; refresh before saving again")
            now = datetime.now(UTC).isoformat()
            values = (
                agent_id,
                framework,
                update.revision + 1,
                update.applicability,
                update.rationale.strip(),
                now,
            )
            db.execute("INSERT OR REPLACE INTO compliance_scope VALUES (?,?,?,?,?,?)", values)
            db.execute(
                "INSERT INTO compliance_scope_history VALUES (?,?,?,?,?,?,?)",
                (*values, "local-reviewer"),
            )
        return self.security(agent_id)

    def review(self, action_id: str, approve: bool):
        with self.connection() as db:
            # Serialize concurrent reviewers before reading the pending state.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
            if row is None:
                raise KeyError(action_id)
            if row["outcome"] != "pending":
                raise ValueError("Only pending actions can be reviewed; decisions are one-time.")
            if approve:
                policy = self._policy(db, row["agent_id"])
                if row["policy_revision"] != policy["revision"]:
                    raise ValueError(
                        "Rules changed since this request. Reject it and submit a new request under the current rules."
                    )
                call = ToolCall(
                    run_id=row["run_id"], tool=row["tool"], arguments=json.loads(row["arguments"])
                )
                if evaluate(call, row["agent_id"], policy["rules"]).outcome == "denied":
                    raise ValueError("Current rules no longer permit this request.")
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
