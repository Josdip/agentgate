import os
import stat

from agentgate.__main__ import main


def test_launcher_creates_private_credentials_and_preserves_them(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGENTGATE_AGENT_TOKEN", raising=False)
    monkeypatch.delenv("AGENTGATE_REVIEWER_TOKEN", raising=False)
    monkeypatch.delenv("AGENTGATE_DB", raising=False)
    calls = []
    monkeypatch.setattr(
        "agentgate.__main__.uvicorn.run", lambda app, **kwargs: calls.append(kwargs)
    )
    main()
    credentials = (tmp_path / ".env").read_text()
    assert stat.S_IMODE((tmp_path / ".env").stat().st_mode) == 0o600
    assert len(os.environ["AGENTGATE_AGENT_TOKEN"]) >= 24
    assert os.environ["AGENTGATE_AGENT_TOKEN"] != os.environ["AGENTGATE_REVIEWER_TOKEN"]
    main()
    assert (tmp_path / ".env").read_text() == credentials
    assert calls == [{"host": "127.0.0.1", "port": 8000}] * 2
