"""Discover local Sonar and start an isolated copy of its original source."""

import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from .client import NoRedirect

MODULES = (
    "sonar",
    "sonar_agent",
    "sonar_tools",
    "sonar_rag",
    "sonar_projects",
    "sonar_github",
    "sonar_desktop",
    "sonar_xwayland",
)


def local_sonar(source, port):
    # A known script and working tree are discovery evidence, not enrollment.
    with Path("/proc/net/tcp").open() as table:
        listeners = {
            f"socket:[{fields[9]}]"
            for line in list(table)[1:]
            if (fields := line.split())[1] == f"0100007F:{port:04X}" and fields[3] == "0A"
        }
    if not listeners:
        return False
    for process in Path("/proc").iterdir():
        if not process.name.isdecimal():
            continue
        try:
            args = (process / "cmdline").read_bytes().split(b"\0")
            if len(args) < 2 or Path(os.fsdecode(args[1])).name != "sonar.py":
                continue
            if (process / "cwd").resolve(strict=True) != source:
                continue
            if any(os.readlink(fd) in listeners for fd in (process / "fd").iterdir()):
                return True
        except OSError:
            continue
    return False


class SonarLauncher:
    def __init__(self, source, state, token_file, gateway_port, standalone_port, managed_port):
        if not all(1 <= port <= 65535 for port in (gateway_port, standalone_port, managed_port)):
            raise ValueError("Invalid local service port.")
        if len({gateway_port, standalone_port, managed_port}) != 3:
            raise ValueError("Use a different port for each local service.")
        self.source = Path(source).expanduser().resolve()
        self.state = Path(state).resolve()
        self.token_file = Path(token_file).resolve()
        self.gateway_port = gateway_port
        self.standalone_port = standalone_port
        self.managed_port = managed_port
        self.process = None
        self.lock = threading.Lock()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.managed_port}"

    def running(self):
        return self.process is not None and self.process.poll() is None

    def discover(self):
        return local_sonar(self.source, self.standalone_port)

    def enroll(self):
        with self.lock:
            if self.running():
                return
            if not self.discover():
                raise ValueError("Run standalone Sonar and scan again.")
            with socket.socket() as probe:
                try:
                    probe.bind(("127.0.0.1", self.managed_port))
                except OSError as exc:
                    raise ValueError("The managed Sonar port is already in use.") from exc
            self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
            script = Path(__file__).with_name("sonar_runtime.py")
            command = [
                "bwrap",
                "--unshare-all",
                "--share-net",
                "--die-with-parent",
                "--clearenv",
                "--ro-bind",
                "/usr",
                "/usr",
                "--symlink",
                "usr/lib",
                "/lib",
                "--symlink",
                "usr/lib64",
                "/lib64",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--tmpfs",
                "/tmp",
                "--dir",
                "/project",
                "--ro-bind",
                str(script),
                "/launch.py",
                "--ro-bind",
                str(self.source / "templates" / "index.html"),
                "/sonar/templates/index.html",
                "--ro-bind",
                str(self.token_file),
                "/broker-token",
                "--bind",
                str(self.state),
                "/state",
            ]
            for module in MODULES:
                name = f"{module}.py"
                command.extend(["--ro-bind", str(self.source / name), f"/sonar/{name}"])
            command.extend(
                [
                    "--setenv",
                    "SONAR_DB",
                    "/state/chat.sqlite3",
                    "--setenv",
                    "SONAR_PORT",
                    str(self.managed_port),
                    "--setenv",
                    "OLLAMA_URL",
                    "http://127.0.0.1:11434",
                    "--setenv",
                    "PYTHONDONTWRITEBYTECODE",
                    "1",
                    "--chdir",
                    "/sonar",
                    "/usr/bin/python3",
                    "/launch.py",
                    str(self.gateway_port),
                ]
            )
            try:
                with (self.state / "launcher.log").open("ab") as log:
                    self.process = subprocess.Popen(
                        command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT
                    )
            except OSError as exc:
                raise ValueError(
                    "Could not start Bubblewrap. Check the launcher prerequisites."
                ) from exc
            opener = build_opener(ProxyHandler({}), NoRedirect())
            for _ in range(30):
                if not self.running():
                    break
                try:
                    with opener.open(self.url + "/local-launch-ready", timeout=0.25) as health:
                        if health.read(64) == b"ready":
                            return
                except (URLError, OSError):
                    time.sleep(0.1)
            self.stop()
            raise ValueError(f"Managed Sonar failed to start. See {self.state / 'launcher.log'}.")

    def stop(self):
        if self.running():
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
