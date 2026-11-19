"""Launcher-owned adapter installed at runtime without editing Sonar's source."""

import json
import os
import sys
import time
from pathlib import Path
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import uuid4

SUPPORTED = {"read_file", "write_file"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def broker(gateway_port, token, name, args, cancel):
    if name not in SUPPORTED or not isinstance(args, dict) or "tool" in args:
        return "Blocked: this operation is unavailable. Continue any independent steps."
    opener = build_opener(ProxyHandler({}), NoRedirect())
    url = f"http://127.0.0.1:{gateway_port}/api/proposals/{uuid4()}"
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

    def settings(module, body):
        for name in ("terminal", "desktop", "github", "rag", "web"):
            body[name] = False
        body["project"] = body["rag_path"] = "/project"
        return original_settings(module, body)

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

    sonar_agent.settings = settings
    sonar_tools.available = available
    sonar_tools.prepare = prepare
    sonar.init_db()
    sonar.app.run(host="127.0.0.1", port=int(os.environ["SONAR_PORT"]), debug=False, threaded=True)


if __name__ == "__main__":
    main()
