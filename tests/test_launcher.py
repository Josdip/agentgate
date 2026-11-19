from agentgate.__main__ import main


def test_managed_launcher_reads_separate_token_files_and_listens_on_loopback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("agentgate.__main__.local_port", lambda port: port)
    agent, reviewer = tmp_path / "agent-token", tmp_path / "reviewer-token"
    agent.write_text("a" * 32 + "\n")
    reviewer.write_text("r" * 32 + "\n")
    monkeypatch.setenv("AGENTGATE_PROJECT", str(tmp_path))
    monkeypatch.setenv("AGENTGATE_SONAR_TOKEN_FILE", str(agent))
    monkeypatch.setenv("AGENTGATE_REVIEWER_TOKEN_FILE", str(reviewer))
    monkeypatch.setenv("AGENTGATE_SONAR_PORT", "5001")
    for name in ("AGENTGATE_PORT", "AGENTGATE_DB"):
        monkeypatch.delenv(name, raising=False)
    configured = []
    listeners = []
    monkeypatch.setattr(
        "agentgate.__main__.create_managed_app",
        lambda *args, **kwargs: configured.append((args, kwargs)),
    )
    monkeypatch.setattr(
        "agentgate.__main__.uvicorn.run", lambda app, **kwargs: listeners.append(kwargs)
    )
    main()
    args, options = configured[0]
    database, project, agent_token, reviewer_token, port = args
    assert options["launcher"].managed_port == 5002
    assert database.name == "discovery.sqlite3"
    assert project == str(tmp_path)
    assert (agent_token, reviewer_token, port) == ("a" * 32, "r" * 32, 5001)
    assert listeners == [{"host": "127.0.0.1", "port": 8001, "proxy_headers": False}]


def test_fresh_demo_launches_have_distinct_tokens_and_empty_inventory(tmp_path, monkeypatch):
    from pathlib import Path

    from fastapi.testclient import TestClient

    monkeypatch.setenv("AGENTGATE_HOME", str(tmp_path))
    monkeypatch.setattr("agentgate.__main__.local_port", lambda port: port)
    monkeypatch.setattr("agentgate.__main__.SonarLauncher.discover", lambda _: True)
    # A demo must never reuse explicitly configured persistent credentials or files.
    monkeypatch.setenv("AGENTGATE_REVIEWER_TOKEN_FILE", str(tmp_path / "do-not-use"))
    results = []

    def launch(app, **kwargs):
        sessions = tmp_path / "demo-sessions"
        session = next(path for path in sessions.iterdir() if path not in results)
        reviewer = {"Authorization": "Bearer " + (session / "reviewer-token").read_text().strip()}
        with TestClient(app) as client:
            if results:
                old_token = (results[0] / "reviewer-token").read_text().strip()
                assert (
                    client.get(
                        "/api/overview", headers={"Authorization": "Bearer " + old_token}
                    ).status_code
                    == 401
                )
            assert client.get("/api/overview", headers=reviewer).json()["agents"] == []
            assert client.post("/api/enrollment", headers=reviewer).status_code == 409
            assert client.post("/api/discovery", headers=reviewer).json()["state"] == "discovered"
            assert (session / "project" / "welcome.txt").is_file()
        assert session.stat().st_mode & 0o777 == 0o700
        results.append(session)

    monkeypatch.setattr("agentgate.__main__.uvicorn.run", launch)
    main(["--fresh-session"])
    main(["--fresh-session"])
    first, second = results
    assert (first / "sonar-token").read_bytes() != (second / "sonar-token").read_bytes()
    assert not Path(tmp_path / "discovery.sqlite3").exists()
