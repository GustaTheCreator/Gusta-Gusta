from fastapi.testclient import TestClient


def test_health_and_page(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<title>Jarvis</title>")
    monkeypatch.setenv("WEB_DIR", str(tmp_path))
    import importlib

    from jarvis import config

    importlib.reload(config)
    from jarvis import server

    importlib.reload(server)
    monkeypatch.setattr(server, "get_model", lambda name: None)
    with TestClient(server.app) as client:
        assert client.get("/api/health").json() == {"ok": True}
        assert "Jarvis" in client.get("/").text
        assert "Jarvis" in client.get("/qualquer/rota").text
        assert client.get("/../../etc/passwd").status_code in (200, 404)
