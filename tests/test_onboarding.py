import socket
import sqlite3
from contextlib import closing

import pytest

from agentgate import onboarding
from agentgate.sonar_launcher import preserve_history


def test_fresh_setup_is_private_and_reuses_state(tmp_path):
    env = {"AGENTGATE_HOME": str(tmp_path / "agentgate")}
    onboarding.setup_paths(env)
    reviewer = tmp_path / "agentgate" / "reviewer-token"
    first = reviewer.read_text()
    assert len(first.strip()) >= 32
    assert reviewer.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "agentgate" / "sonar-token").read_text() != first
    assert (tmp_path / "agentgate" / "project" / "welcome.txt").is_file()
    onboarding.setup_paths({"AGENTGATE_HOME": env["AGENTGATE_HOME"]})
    assert reviewer.read_text() == first


def test_history_snapshot_copies_live_wal_and_keeps_both_databases_separate(tmp_path):
    original = tmp_path / "original.sqlite3"
    managed = tmp_path / "managed"
    managed.mkdir()
    with closing(sqlite3.connect(original)) as standalone:
        standalone.execute("PRAGMA journal_mode=WAL")
        standalone.execute("CREATE TABLE history (message TEXT)")
        standalone.execute("INSERT INTO history VALUES ('before enrollment')")
        standalone.commit()
        preserve_history(original, managed)
        copy = managed / "chat.sqlite3"
        with closing(sqlite3.connect(copy)) as database:
            assert database.execute("SELECT message FROM history").fetchall() == [
                ("before enrollment",)
            ]
            database.execute("INSERT INTO history VALUES ('managed only')")
            database.commit()
        assert standalone.execute("SELECT COUNT(*) FROM history").fetchone() == (1,)
        preserve_history(original, managed)
        with closing(sqlite3.connect(copy)) as database:
            assert database.execute("SELECT COUNT(*) FROM history").fetchone() == (2,)
    with pytest.raises(ValueError, match="different Sonar history"):
        preserve_history(tmp_path / "another.sqlite3", managed)


def test_configured_sandbox_never_requests_sudo(monkeypatch):
    monkeypatch.setattr(onboarding, "sandbox_probe", lambda: "")
    monkeypatch.setattr(
        onboarding.subprocess, "run", lambda *a, **k: pytest.fail("Unexpected host change")
    )
    onboarding.setup_sandbox()


def test_denied_sandbox_without_approval_fails_closed(tmp_path, monkeypatch):
    restriction = tmp_path / "restriction"
    restriction.write_text("1")
    monkeypatch.setattr(onboarding, "sandbox_probe", lambda: "uid map: Permission denied")
    original_path = onboarding.Path
    monkeypatch.setattr(
        onboarding,
        "Path",
        lambda path: restriction if str(path).startswith("/proc/sys/") else original_path(path),
    )
    monkeypatch.setattr(onboarding, "PROFILE", tmp_path / "profile")
    monkeypatch.setattr(onboarding.shutil, "which", lambda _: "/usr/bin/bwrap")
    monkeypatch.setattr(onboarding.subprocess, "run", lambda *a, **k: pytest.fail("No approval"))
    monkeypatch.setattr("builtins.input", lambda _: "no")
    with pytest.raises(ValueError, match="skipped"):
        onboarding.setup_sandbox()


def test_ubuntu_installer_loads_scoped_profile_and_rechecks(tmp_path, monkeypatch):
    restriction = tmp_path / "restriction"
    restriction.write_text("1")
    checks = iter(["uid map: Permission denied", ""])
    monkeypatch.setattr(onboarding, "sandbox_probe", lambda: next(checks))
    original_path = onboarding.Path
    monkeypatch.setattr(
        onboarding,
        "Path",
        lambda path: restriction if str(path).startswith("/proc/sys/") else original_path(path),
    )
    profile = tmp_path / "agentgate-bwrap"
    monkeypatch.setattr(onboarding, "PROFILE", profile)
    monkeypatch.setattr(onboarding.shutil, "which", lambda _: "/usr/bin/bwrap")
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    commands = []

    def run(args, check):
        assert check
        commands.append(args)
        if args[1] == "install":
            assert original_path(args[-2]).read_text() == onboarding.POLICY
            assert args[-1] == str(profile)

    monkeypatch.setattr(onboarding.subprocess, "run", run)
    onboarding.setup_sandbox()
    assert commands[-1] == ["sudo", "/usr/sbin/apparmor_parser", "-r", str(profile)]
    assert restriction.read_text() == "1"


def test_default_listener_uses_free_port_when_occupied():
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        assigned = onboarding.local_port(occupied.getsockname()[1])
        assert assigned != occupied.getsockname()[1]
        with socket.socket() as alternate:
            alternate.bind(("127.0.0.1", assigned))
