"""HTTP boundary. Construct via uvicorn's factory mode after setting credentials."""

import os
import secrets
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .policy import StrictModel, ToolCall
from .profile import ProfileUpdate
from .scenarios import scenario, scenarios
from .store import Store

bearer = HTTPBearer(auto_error=False)


class Review(StrictModel):
    approve: bool


def create_app(db_path=None, agent_token=None, reviewer_token=None):
    agent_token = agent_token or os.environ.get("AGENTGATE_AGENT_TOKEN", "")
    reviewer_token = reviewer_token or os.environ.get("AGENTGATE_REVIEWER_TOKEN", "")
    if min(len(agent_token), len(reviewer_token)) < 24 or agent_token == reviewer_token:
        raise RuntimeError(
            "Configure distinct agent and reviewer tokens of at least 24 characters."
        )
    store = Store(db_path or os.environ.get("AGENTGATE_DB", "data/agentgate.db"))
    app = FastAPI(
        title="AgentGate",
        version="0.1.0",
        description="Synthetic tool governance demo",
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"]
    )
    static = Path(__file__).parent / "static"

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        size = request.headers.get("content-length")
        if size and (not size.isdigit() or int(size) > 16384):
            return JSONResponse({"detail": "Request too large or invalid length"}, status_code=413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    def require(expected):
        def check(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
            if credentials is None or not secrets.compare_digest(credentials.credentials, expected):
                raise HTTPException(
                    401, "Invalid credentials", headers={"WWW-Authenticate": "Bearer"}
                )

        return check

    agent_auth = Depends(require(agent_token))
    reviewer_auth = Depends(require(reviewer_token))

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def invalid_arguments(request, exc):
        # Avoid echoing potentially sensitive parameter values in validation errors.
        return JSONResponse({"detail": "Invalid tool arguments"}, status_code=422)

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "synthetic"}

    @app.post("/api/actions", dependencies=[agent_auth], status_code=201)
    def submit(call: ToolCall):
        return store.submit(call)

    @app.get("/api/actions", dependencies=[reviewer_auth])
    def actions():
        return store.list()

    @app.post("/api/actions/{action_id}/review", dependencies=[reviewer_auth])
    def review(action_id: str, decision: Review):
        try:
            return store.review(action_id, decision.approve)
        except KeyError:
            raise HTTPException(404, "Action not found") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/api/agent", dependencies=[reviewer_auth])
    def agent_profile():
        return store.profile()

    @app.put("/api/agent", dependencies=[reviewer_auth])
    def update_agent_profile(update: ProfileUpdate):
        try:
            return store.update_profile(update)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.get("/api/demo/scenarios", dependencies=[reviewer_auth])
    def demo_scenarios():
        return scenarios()

    @app.post(
        "/api/demo/scenarios/{scenario_id}/run", dependencies=[reviewer_auth], status_code=201
    )
    async def run_scenario(scenario_id: str, request: Request):
        # No caller-supplied tools/arguments or identities at this reviewer-only boundary.
        if await request.body():
            raise HTTPException(422, "Scenario runs do not accept a request body")
        selected = scenario(scenario_id)
        if selected is None:
            raise HTTPException(404, "Scenario not found")
        action = store.submit(
            ToolCall(
                run_id=f"demo-{selected['id']}-{uuid4().hex[:8]}",
                tool=selected["tool"],
                arguments=selected["arguments"],
            )
        )
        return {
            "scenario_id": scenario_id,
            "expected": selected["expected"],
            "matched": action["outcome"] == selected["expected"],
            "action": action,
        }

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(static / "index.html")

    app.mount("/static", StaticFiles(directory=static), name="static")
    return app
