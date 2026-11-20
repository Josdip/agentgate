"""Launcher-owned adapter installed at runtime without editing Sonar's source."""

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

SUPPORTED = {"read_file", "write_file"}


PROJECT_PATH = r"(?:/project/)?[A-Za-z0-9_-][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*"
READ_COMMAND = re.compile(
    rf"read `?(?P<path>{PROJECT_PATH})`?(?: and tell me what it says)?[.!?]?", re.IGNORECASE
)
WRITE_COMMAND = re.compile(
    rf'write "(?P<content>[^"\r\n]*)" to `?(?P<path>{PROJECT_PATH})`?[.!?]?', re.IGNORECASE
)


def project_command(message):
    for tool, pattern in (("read_file", READ_COMMAND), ("write_file", WRITE_COMMAND)):
        if match := pattern.fullmatch(
            message.strip().removesuffix(".").removesuffix("!").removesuffix("?")
        ):
            return tool, match.groupdict()
    return None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def broker(gateway_port, token, name, args, cancel):
    if name not in SUPPORTED or not isinstance(args, dict) or "tool" in args:
        return "Blocked: this operation is unavailable. Continue any independent steps."
    opener = build_opener(ProxyHandler({}), NoRedirect())
    url = f"http://127.0.0.1:{gateway_port}/api/proposals/{uuid4()}"
    args = dict(args)
    path = args.get("path")
    if isinstance(path, str) and path.startswith("/project/"):
        args["path"] = path.removeprefix("/project/")
    payload = json.dumps({"tool": name, **args}).encode()

    def call(method, suffix="", data=None):
        request = Request(
            url + suffix,
            method=method,
            data=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with opener.open(request, timeout=5) as response:
            return json.load(response)

    deadline = time.monotonic() + 300
    try:
        if cancel.is_set():
            return "Action stopped."
        state = call("PUT", data=payload)["status"]
        while state == "pending" and time.monotonic() < deadline:
            if cancel.wait(1):
                return "Action stopped."
            state = call("GET")["status"]
        if not cancel.is_set() and state == "ready" and time.monotonic() < deadline:
            result = call("POST", "/execute", payload)
            if result["status"] == "executed":
                return result["result"] or "(No lines in the requested range.)"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return "Blocked: permission denied or the file operation could not complete. Continue any independent steps."


def main():
    sys.path.insert(0, "/sonar")
    import sonar
    import sonar_agent
    import sonar_tools
    from flask import request

    token = Path("/broker-token").read_text().strip()
    gateway_port = int(sys.argv[1])
    original_settings = sonar_agent.settings
    original_available = sonar_tools.available

    def settings(module, body, *args, **kwargs):
        for name in ("terminal", "desktop", "github", "rag", "web"):
            body[name] = False
        body["project"] = body["rag_path"] = "/project"
        return original_settings(module, body, *args, **kwargs)

    def available(config):
        return [
            item for item in original_available(config) if item["function"]["name"] in SUPPORTED
        ]

    def prepare(root, name, args):
        # The original worker calls prepare before its built-in review loop.
        # A completed result bypasses that review, and no Sonar tool executes locally.
        cancel = next(iter(sonar_agent.RUNS.values()))["cancel"]
        return {"result": broker(gateway_port, token, name, args, cancel)}

    @sonar.app.before_request
    def disable_alternate_routes():
        if request.path.startswith("/api/rag/") or request.path.endswith("/approval"):
            return {"error": "This operation is unavailable."}, 403
        return None

    @sonar.app.get("/local-launch-ready")
    def ready():
        return "ready"

    if hasattr(sonar_agent, "direct_action") and hasattr(sonar_agent, "run_direct_action"):
        original_direct = sonar_agent.direct_action
        original_run_direct = sonar_agent.run_direct_action

        def direct_action(message):
            return project_command(message) or original_direct(message)

        def run_direct_action(run, config, audit, emit):
            name, args = run["direct"]
            if name not in SUPPORTED:
                return original_run_direct(run, config, audit, emit)
            if not config.get("tools") or not config.get("files"):
                return "Enable tools and project file access to use this command."
            return broker(gateway_port, token, name, args, run["cancel"])

        sonar_agent.direct_action = direct_action
        sonar_agent.run_direct_action = run_direct_action

    sonar_agent.settings = settings
    sonar_tools.available = available
    sonar_tools.prepare = prepare
    sonar.init_db()
    sonar.app.run(host="127.0.0.1", port=int(os.environ["SONAR_PORT"]), debug=False, threaded=True)


if __name__ == "__main__":
    main()
