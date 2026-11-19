"""First-run local settings and sandbox prerequisite checks."""

import os
import secrets
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

PROFILE = Path("/etc/apparmor.d/agentgate-bwrap")
POLICY = """abi <abi/4.0>,
include <tunables/global>

profile agentgate-bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
}
"""


def local_port(default):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        for port in (default, 0):
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                continue
            return listener.getsockname()[1]
    raise ValueError("Could not reserve a local port.")


def private_token(path):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path
    with os.fdopen(fd, "w") as file:
        file.write(secrets.token_urlsafe(32) + "\n")
    return path


def setup_paths(environ):
    if all(
        environ.get(key)
        for key in (
            "AGENTGATE_DB",
            "AGENTGATE_PROJECT",
            "AGENTGATE_SONAR_TOKEN_FILE",
            "AGENTGATE_REVIEWER_TOKEN_FILE",
        )
    ):
        return
    default = Path(environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "agentgate"
    home = Path(environ.get("AGENTGATE_HOME", default)).expanduser()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    if "AGENTGATE_PROJECT" not in environ:
        project = home / "project"
        project.mkdir(mode=0o700, exist_ok=True)
        try:
            with (project / "welcome.txt").open("x") as file:
                file.write("Hello from the protected project.\n")
        except FileExistsError:
            pass
        environ["AGENTGATE_PROJECT"] = str(project)
    environ.setdefault("AGENTGATE_DB", str(home / "discovery.sqlite3"))
    for key, filename in (
        ("AGENTGATE_SONAR_TOKEN_FILE", "sonar-token"),
        ("AGENTGATE_REVIEWER_TOKEN_FILE", "reviewer-token"),
    ):
        if key not in environ:
            environ[key] = str(private_token(home / filename))


def sandbox_probe():
    executable = shutil.which("bwrap")
    if executable is None:
        return "Bubblewrap is missing. Install your system's bubblewrap package, then run ./start-local."
    try:
        result = subprocess.run(
            [
                executable,
                "--unshare-all",
                "--share-net",
                "--die-with-parent",
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
                "--",
                "/usr/bin/true",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "Bubblewrap could not run its sandbox check."
    return result.stderr.strip() if result.returncode else ""


def setup_sandbox():
    problem = sandbox_probe()
    if not problem:
        return
    restriction = Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns")
    system_bwrap = shutil.which("bwrap")
    if (
        "Permission denied" not in problem
        or not restriction.exists()
        or restriction.read_text().strip() != "1"
        or not system_bwrap
        or Path(system_bwrap).resolve() != Path("/usr/bin/bwrap")
    ):
        raise ValueError(problem)
    installed = PROFILE.exists()
    if PROFILE.is_symlink() or (installed and PROFILE.read_text() != POLICY):
        raise ValueError(
            f"Bubblewrap is blocked even with {PROFILE}. Ask an administrator to check that profile."
        )
    print("Ubuntu requires a one-time administrator approval for Bubblewrap.")
    print(
        "This gives /usr/bin/bwrap permission to create user namespaces and leaves the system-wide setting enabled."
    )
    try:
        reply = input("Install the Bubblewrap AppArmor profile? [y/N] ").strip().lower()
    except EOFError:
        reply = ""
    if reply not in {"y", "yes"}:
        raise ValueError("Sandbox setup was skipped. Run ./start-local to try again.")
    try:
        if not installed:
            with tempfile.TemporaryDirectory() as directory:
                staged = Path(directory) / PROFILE.name
                staged.write_text(POLICY)
                subprocess.run(
                    [
                        "sudo",
                        "install",
                        "-o",
                        "root",
                        "-g",
                        "root",
                        "-m",
                        "0644",
                        str(staged),
                        str(PROFILE),
                    ],
                    check=True,
                )
        subprocess.run(["sudo", "/usr/sbin/apparmor_parser", "-r", str(PROFILE)], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(
            "Could not install the Bubblewrap profile. Try again with administrator access."
        ) from exc
    if problem := sandbox_probe():
        raise ValueError(f"Bubblewrap still cannot start: {problem}")
