"""Local discovery, reviewer policy, and a file executor for managed Sonar."""

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager, closing, contextmanager
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .client import NoRedirect
from .cloud import CloudInventoryError, bedrock_agents
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


class ChromeObservation(StrictModel):
    service: Literal["chatgpt"]


class BedrockScan(StrictModel):
    region: str = Field(pattern=r"^[a-z]{2}(?:-[a-z0-9]+)+-[0-9]+$", max_length=40)
    profile: str = Field(default="", pattern=r"^(?:[A-Za-z0-9][A-Za-z0-9_.-]{0,63})?$")


class CloudEnrollment(BedrockScan):
    scope: str = Field(max_length=100)
    agent_id: str = Field(pattern=r"^[a-zA-Z0-9]{10}$")


class BrowserConnection(StrictModel):
    code: str = Field(min_length=1, max_length=128)


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
                CREATE TABLE IF NOT EXISTS external_agents (
                    connector TEXT NOT NULL, scope TEXT NOT NULL, external_id TEXT NOT NULL,
                    name TEXT NOT NULL, provider_status TEXT NOT NULL, scanned REAL NOT NULL,
                    PRIMARY KEY (connector, scope, external_id)
                );
                CREATE TABLE IF NOT EXISTS external_enrollment (
                    connector TEXT NOT NULL, scope TEXT NOT NULL, external_id TEXT NOT NULL,
                    credential_hash TEXT, PRIMARY KEY (connector,scope,external_id)
                );
                CREATE TABLE IF NOT EXISTS actions (
                    id TEXT PRIMARY KEY, tool TEXT NOT NULL, path TEXT NOT NULL,
                    digest TEXT NOT NULL, size INTEGER, created REAL NOT NULL,
                    decision TEXT NOT NULL, status TEXT NOT NULL, revision INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS action_reviews (
                    action_id TEXT PRIMARY KEY, reviewer TEXT NOT NULL,
                    decision TEXT NOT NULL, reviewed_at REAL NOT NULL
                );
                """)

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            yield db

    def record_external(self, connector, scope, agents):
        with self.transaction() as db:
            db.execute(
                "DELETE FROM external_agents WHERE connector=? AND scope=?", (connector, scope)
            )
            scanned = time.time()
            db.executemany(
                "INSERT INTO external_agents VALUES (?,?,?,?,?,?)",
                [
                    (connector, scope, identifier, name, state, scanned)
                    for identifier, name, state in agents
                ],
            )
            db.execute(
                """DELETE FROM external_enrollment WHERE connector=? AND scope=? AND NOT EXISTS (
                    SELECT 1 FROM external_agents a WHERE a.connector=external_enrollment.connector
                    AND a.scope=external_enrollment.scope AND a.external_id=external_enrollment.external_id)""",
                (connector, scope),
            )

    def invalid(self, action_id, tool):
        with self.transaction() as db:
            db.execute(
                """INSERT OR IGNORE INTO actions
                (id, tool, path, digest, size, created, decision, status, revision)
                SELECT ?, tool, '[Invalid project path or arguments]', '', NULL, ?,
                       'invalid request', 'denied', revision FROM rules WHERE tool=?""",
                (action_id, time.time(), tool),
            )

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
    database,
    project,
    agent_token,
    reviewer_token,
    sonar_port=5000,
    *,
    launcher=None,
    first_run_code=None,
    bedrock_fixture=False,
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
    first_run_lock = Lock()
    first_run_expires = time.monotonic() + 300
    connector_lock = Lock()
    chrome_code = ""
    chrome_expires = 0.0
    pairing_code = ""
    pairing_expires = 0.0

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
        # Retain only a safe label when a real agent submits malformed tool arguments.
        body = exc.body
        request_id = request.path_params.get("request_id")
        if (
            request.method == "PUT"
            and request.url.path.startswith("/api/proposals/")
            and request_id
            and isinstance(body, dict)
            and isinstance(body.get("tool"), str)
            and body["tool"] in {"read_file", "write_file"}
            and hmac.compare_digest(
                request.headers.get("Authorization", "").encode(), f"Bearer {agent_token}".encode()
            )
            and (launcher is None or launcher.running())
        ):
            try:
                action_id = str(UUID(request_id))
            except ValueError:
                pass
            else:
                # Use the worker thread like the other disk-bound API handlers.
                await run_in_threadpool(ledger.invalid, action_id, body["tool"])
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

    @app.post("/api/first-run/connection")
    def first_run_connection(connection: BrowserConnection):
        nonlocal first_run_code
        with first_run_lock:
            if (
                not first_run_code
                or time.monotonic() >= first_run_expires
                or not hmac.compare_digest(connection.code.encode(), first_run_code.encode())
            ):
                raise HTTPException(
                    401, "The one-use link is invalid or expired. Use the reviewer token."
                )
            first_run_code = None
        return {"token": reviewer_token}

    @app.post("/api/connectors/chrome/code", dependencies=[reviewer])
    def new_chrome_code():
        nonlocal chrome_code, chrome_expires
        code = secrets.token_urlsafe(32)
        with connector_lock:
            chrome_code = code
            chrome_expires = time.monotonic() + 600
        return {"code": code, "expires_in": 600}

    @app.post("/api/connectors/chrome/observation")
    def observe_chrome(observation: ChromeObservation, authorization: str = Header(default="")):
        nonlocal chrome_code
        with connector_lock:
            if (
                not chrome_code
                or time.monotonic() >= chrome_expires
                or not hmac.compare_digest(authorization.encode(), f"Bearer {chrome_code}".encode())
            ):
                raise HTTPException(401, "Invalid Chrome discovery code.")
            ledger.record_external(
                "chrome",
                "This browser",
                [(observation.service, "ChatGPT", "Tab observed")],
            )
            chrome_code = ""
        return {"recorded": True}

    @app.post("/api/connectors/chrome/enrollment-code", dependencies=[reviewer])
    def chrome_enrollment_code():
        nonlocal pairing_code, pairing_expires
        with connector_lock, ledger.transaction() as db:
            if not db.execute("SELECT 1 FROM external_agents WHERE connector='chrome'").fetchone():
                raise HTTPException(409, "Discover ChatGPT before enrolling Chrome.")
            pairing_code = secrets.token_urlsafe(32)
            pairing_expires = time.monotonic() + 600
            return {"code": pairing_code}

    @app.post("/api/connectors/chrome/enrollment")
    def enroll_chrome(observation: ChromeObservation, authorization: str = Header(default="")):
        nonlocal pairing_code
        with connector_lock, ledger.transaction() as db:
            if (
                not pairing_code
                or time.monotonic() >= pairing_expires
                or not hmac.compare_digest(
                    authorization.encode(), f"Bearer {pairing_code}".encode()
                )
            ):
                raise HTTPException(401, "Invalid Chrome enrollment code.")
            credential = secrets.token_urlsafe(32)
            db.execute(
                "INSERT OR REPLACE INTO external_enrollment VALUES ('chrome','This browser',?,?)",
                (observation.service, hashlib.sha256(credential.encode()).hexdigest()),
            )
            pairing_code = ""
        return {"credential": credential}

    @app.post("/api/connectors/chrome/report")
    def report_chrome(observation: ChromeObservation, authorization: str = Header(default="")):
        scheme, _, credential = authorization.partition(" ")
        digest = hashlib.sha256(credential.encode()).hexdigest()
        reported_at = time.time()
        with ledger.transaction() as db:
            bound = db.execute(
                "SELECT credential_hash FROM external_enrollment WHERE connector='chrome' AND scope='This browser' AND external_id=?",
                (observation.service,),
            ).fetchone()
            if scheme != "Bearer" or not bound or not hmac.compare_digest(bound[0], digest):
                raise HTTPException(401, "Chrome enrollment is missing or revoked.")
            db.execute(
                "UPDATE external_agents SET scanned=?, provider_status='Enrolled report received' WHERE connector='chrome' AND scope='This browser' AND external_id=?",
                (reported_at, observation.service),
            )
        return {"recorded": True, "reported_at": reported_at}

    @app.delete("/api/connectors/chrome/enrollment", dependencies=[reviewer])
    def revoke_chrome():
        nonlocal pairing_code
        with connector_lock, ledger.transaction() as db:
            pairing_code = ""
            db.execute("DELETE FROM external_enrollment WHERE connector='chrome'")
            db.execute(
                "UPDATE external_agents SET provider_status='Tab observed' WHERE connector='chrome'"
            )
        return {"revoked": True}

    def cloud_inventory(scan):
        if bedrock_fixture:
            return (
                "bedrock-fixture",
                f"Demo fixture · {scan.region}",
                [("DEMOAGENT1", "Example Bedrock Agent", "PREPARED")],
            )
        try:
            account, agents = bedrock_agents(scan.region, scan.profile)
        except CloudInventoryError as exc:
            raise HTTPException(409, str(exc)) from None
        return "bedrock", f"{account} · {scan.region}", agents

    @app.post("/api/connectors/bedrock/discovery", dependencies=[reviewer])
    def scan_bedrock(scan: BedrockScan):
        connector, scope, agents = cloud_inventory(scan)
        ledger.record_external(connector, scope, agents)
        return {"count": len(agents)}

    @app.post("/api/connectors/bedrock/enrollment", dependencies=[reviewer])
    def enroll_bedrock(selection: CloudEnrollment):
        with ledger.transaction() as db:
            if not db.execute(
                "SELECT 1 FROM external_agents WHERE connector IN ('bedrock','bedrock-fixture') AND scope=? AND external_id=?",
                (selection.scope, selection.agent_id),
            ).fetchone():
                raise HTTPException(409, "Discover the Bedrock agent before enrollment.")
        connector, scope, agents = cloud_inventory(selection)
        if scope != selection.scope or not any(agent[0] == selection.agent_id for agent in agents):
            raise HTTPException(
                409, "The selected agent could not be verified in that account and region."
            )
        with ledger.transaction() as db:
            db.execute(
                "INSERT OR REPLACE INTO external_enrollment VALUES (?,?,?,NULL)",
                (connector, scope, selection.agent_id),
            )
        return {"enrolled": True}

    @app.delete("/api/connectors/bedrock/enrollment", dependencies=[reviewer])
    def revoke_bedrock(selection: CloudEnrollment):
        with ledger.transaction() as db:
            db.execute(
                "DELETE FROM external_enrollment WHERE connector IN ('bedrock','bedrock-fixture') AND scope=? AND external_id=?",
                (selection.scope, selection.agent_id),
            )
        return {"revoked": True}

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
                "bedrock_fixture": bedrock_fixture,
                "external_agents": [
                    dict(row)
                    for row in db.execute(
                        """SELECT a.*, e.external_id IS NOT NULL AS enrolled FROM external_agents a
                        LEFT JOIN external_enrollment e USING (connector,scope,external_id)
                        ORDER BY a.connector,a.scope,a.name,a.external_id"""
                    )
                ],
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
                    for row in db.execute("""SELECT a.*, r.reviewer, r.decision AS review_decision, r.reviewed_at
                        FROM actions a LEFT JOIN action_reviews r ON r.action_id=a.id
                        ORDER BY a.rowid DESC LIMIT 100""")
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
            db.execute(
                "INSERT INTO action_reviews VALUES (?,?,?,?)",
                (
                    str(request_id),
                    "local-reviewer",
                    "approved" if review.approve else "rejected",
                    time.time(),
                ),
            )
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
