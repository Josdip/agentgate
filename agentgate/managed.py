"""Local discovery, reviewer policy, and a file executor for managed Sonar."""

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager, closing, contextmanager
from pathlib import Path
from typing import Annotated, Literal
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .client import NoRedirect
from .policy import StrictModel
from .project_files import MAX_BYTES, ProjectFiles, relative_path

Mode = Literal["allow", "deny", "review"]
Tool = Literal["read_file", "write_file"]
STATIC = Path(__file__).parent / "static"
TTL = 300


class Action(StrictModel):
    tool: Tool
    path: str = Field(min_length=1, max_length=300)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value):
        relative_path(value)
        return value


class Read(Action):
    tool: Literal["read_file"]
    start_line: int = Field(default=1, ge=1, le=128_000)
    line_count: int = Field(default=100, ge=1, le=200)


class Write(Action):
    tool: Literal["write_file"]
    content: str = Field(max_length=MAX_BYTES)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value):
        if len(value.encode()) > MAX_BYTES or "\0" in value:
            raise ValueError("Expected bounded UTF-8 text.")
        return value


Proposal = Annotated[Read | Write, Field(discriminator="tool")]


class Rule(StrictModel):
    mode: Mode


class Review(StrictModel):
    approve: bool


def discover_sonar(port, token):
    challenge = secrets.token_hex(32)
    url = f"http://127.0.0.1:{port}/api/agentgate/discovery?challenge={challenge}"
    try:
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(
            Request(url, headers={"Accept": "application/json"}), timeout=2
        ) as response:
            document = json.loads(response.read(4096))
    except (URLError, OSError, ValueError):
        return "offline"
    if not isinstance(document, dict) or document.get("protocol") != "agentgate-sonar-v1":
        return "offline"
    expected = hmac.digest(
        token.encode(), f"agentgate-sonar-v1:{challenge}".encode(), "sha256"
    ).hex()
    proof = document.get("proof")
    if isinstance(proof, str) and hmac.compare_digest(proof.encode(), expected.encode()):
        return "managed"
    return "discovered"


class Ledger:
    def __init__(self, path):
        self.path = path
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS discovery (
                    id INTEGER PRIMARY KEY CHECK (id=1), state TEXT, scanned REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rules (
                    tool TEXT PRIMARY KEY, mode TEXT NOT NULL, revision INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO rules VALUES ('read_file', 'review', 1), ('write_file', 'deny', 1);
                CREATE TABLE IF NOT EXISTS actions (
                    id TEXT PRIMARY KEY, tool TEXT NOT NULL, path TEXT NOT NULL,
                    digest TEXT NOT NULL, size INTEGER, created REAL NOT NULL,
                    decision TEXT NOT NULL, status TEXT NOT NULL, revision INTEGER NOT NULL
                );
                """)

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            yield db

    @staticmethod
    def action(db, action_id):
        row = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Request not found.")
        return dict(row)

    @staticmethod
    def public(action):
        action = dict(action)
        if action["status"] in {"pending", "ready"} and time.time() >= action["created"] + TTL:
            action["status"] = "expired"
        return action


def fingerprint(action):
    return hashlib.sha256(action.model_dump_json().encode()).hexdigest()


def create_managed_app(
    database, project, agent_token, reviewer_token, sonar_port=5000, *, launcher=None
):
    if (
        min(len(agent_token), len(reviewer_token)) < 32
        or agent_token == reviewer_token
        or not agent_token.isascii()
        or not reviewer_token.isascii()
    ):
        raise ValueError(
            "Provide separate ASCII agent and reviewer tokens of at least 32 characters."
        )
    if not 1 <= sonar_port <= 65535:
        raise ValueError("Invalid local Sonar port.")
    ledger = Ledger(database)

    @asynccontextmanager
    async def lifespan(app):
        executor = ProjectFiles(project)
        app.state.executor = executor
        try:
            yield
        finally:
            if launcher:
                launcher.stop()
            executor.close()

    app = FastAPI(
        title="AgentGate",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        return JSONResponse({"detail": "Invalid request."}, status_code=422)

    def role(token):
        def authenticate(authorization: str = Header(default="")):
            if not hmac.compare_digest(authorization.encode(), f"Bearer {token}".encode()):
                raise HTTPException(401, "Valid credentials required.")

        return Depends(authenticate)

    reviewer, agent = role(reviewer_token), role(agent_token)

    @app.get("/")
    @app.get("/agents")
    @app.get("/activity")
    @app.get("/rules")
    @app.get("/security")
    def index():
        return FileResponse(STATIC / "managed.html")

    @app.get("/static/{asset}")
    def static_asset(asset: Literal["styles.css", "theme.js", "managed.js"]):
        return FileResponse(STATIC / asset)

    @app.post("/api/discovery", dependencies=[reviewer])
    def scan():
        if launcher:
            state = (
                "managed"
                if launcher.running()
                else ("discovered" if launcher.discover() else "offline")
            )
        else:
            state = discover_sonar(sonar_port, agent_token)
        with ledger.transaction() as db:
            if state != "offline" or db.execute("SELECT 1 FROM discovery").fetchone():
                db.execute(
                    "INSERT OR REPLACE INTO discovery VALUES (1,?,?)",
                    (state, time.time()),
                )
        return {"state": state}

    @app.post("/api/enrollment", dependencies=[reviewer])
    def enroll():
        if launcher is None:
            raise HTTPException(404, "Enrollment is unavailable.")
        with ledger.transaction() as db:
            found = db.execute("SELECT state FROM discovery").fetchone()
            if found is None or found["state"] not in {"discovered", "managed"}:
                raise HTTPException(409, "Scan and discover Sonar before adding it.")
        try:
            launcher.enroll()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        with ledger.transaction() as db:
            db.execute("UPDATE discovery SET state='managed',scanned=? WHERE id=1", (time.time(),))
        return {"state": "managed", "url": launcher.url}

    @app.get("/api/overview", dependencies=[reviewer])
    def overview():
        with ledger.transaction() as db:
            found = db.execute("SELECT state,scanned FROM discovery").fetchone()
            agents = [{"name": "Sonar", **dict(found)}] if found else []
            if launcher and agents and agents[0]["state"] == "managed":
                agents[0]["state"] = "managed" if launcher.running() else "offline"
                if launcher.running():
                    agents[0]["url"] = launcher.url
            return {
                "agents": agents,
                "counts": dict(
                    db.execute(
                        """SELECT COUNT(*) AS total,
                        COUNT(CASE WHEN status='pending' AND created>? THEN 1 END) AS pending,
                        COUNT(CASE WHEN status='denied' THEN 1 END) AS denied,
                        COUNT(CASE WHEN status='executed' THEN 1 END) AS executed FROM actions""",
                        (time.time() - TTL,),
                    ).fetchone()
                ),
                "rules": [dict(row) for row in db.execute("SELECT * FROM rules ORDER BY tool")],
                "activity": [
                    ledger.public(row)
                    for row in db.execute("SELECT * FROM actions ORDER BY rowid DESC LIMIT 100")
                ],
            }

    @app.put("/api/rules/{tool}", dependencies=[reviewer])
    def change_rule(tool: Tool, rule: Rule):
        with ledger.transaction() as db:
            update = db.execute(
                "UPDATE rules SET mode=?,revision=revision+1 WHERE tool=? AND mode<>?",
                (rule.mode, tool, rule.mode),
            )
            if update.rowcount:
                db.execute(
                    "UPDATE actions SET status='superseded' WHERE tool=? AND status IN ('pending','ready')",
                    (tool,),
                )
        return {"mode": rule.mode}

    @app.put("/api/proposals/{request_id}", dependencies=[agent])
    def submit(request_id: UUID, action: Proposal):
        if launcher and not launcher.running():
            raise HTTPException(403, "No managed Sonar instance is running.")
        digest = fingerprint(action)
        with ledger.transaction() as db:
            existing = db.execute("SELECT * FROM actions WHERE id=?", (str(request_id),)).fetchone()
            if existing is not None:
                if existing["digest"] != digest:
                    raise HTTPException(409, "Request ID already binds different arguments.")
                return ledger.public(existing)
            mode, revision = db.execute(
                "SELECT mode,revision FROM rules WHERE tool=?", (action.tool,)
            ).fetchone()
            status = {"allow": "ready", "deny": "denied", "review": "pending"}[mode]
            size = len(action.content.encode()) if isinstance(action, Write) else None
            db.execute(
                "INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(request_id),
                    action.tool,
                    action.path,
                    digest,
                    size,
                    time.time(),
                    mode,
                    status,
                    revision,
                ),
            )
            return ledger.action(db, str(request_id))

    @app.get("/api/proposals/{request_id}", dependencies=[agent])
    def status(request_id: UUID):
        with ledger.transaction() as db:
            return ledger.public(ledger.action(db, str(request_id)))

    @app.post("/api/proposals/{request_id}/review", dependencies=[reviewer])
    def review(request_id: UUID, review: Review):
        with ledger.transaction() as db:
            action = ledger.public(ledger.action(db, str(request_id)))
            if action["status"] != "pending":
                raise HTTPException(409, "This request is no longer waiting for review.")
            revision = db.execute(
                "SELECT revision FROM rules WHERE tool=?", (action["tool"],)
            ).fetchone()[0]
            if review.approve and revision != action["revision"]:
                raise HTTPException(409, "Rule changed. Reject this request and submit a new one.")
            updated = "ready" if review.approve else "rejected"
            db.execute("UPDATE actions SET status=? WHERE id=?", (updated, str(request_id)))
            return {"status": updated}

    @app.post("/api/proposals/{request_id}/execute", dependencies=[agent])
    def execute(request_id: UUID, action: Proposal):
        if launcher and not launcher.running():
            raise HTTPException(403, "No managed Sonar instance is running.")
        action_id = str(request_id)
        with ledger.transaction() as db:
            record = ledger.public(ledger.action(db, action_id))
            if record["digest"] != fingerprint(action) or record["status"] != "ready":
                raise HTTPException(409, "Execution requires the exact authorized request.")
            revision = db.execute(
                "SELECT revision FROM rules WHERE tool=?", (action.tool,)
            ).fetchone()[0]
            if record["revision"] != revision:
                raise HTTPException(409, "Rule changed. Submit a new request.")
            # Commit the claim before any side effect. A crash leaves execution uncertain.
            db.execute("UPDATE actions SET status='executing' WHERE id=?", (action_id,))
        try:
            result = app.state.executor.execute(action)
        except (OSError, ValueError):
            outcome, result = "failed", None
        else:
            outcome = "executed"
        with ledger.transaction() as db:
            db.execute("UPDATE actions SET status=? WHERE id=?", (outcome, action_id))
        return {"status": outcome, "result": result}

    return app
