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
