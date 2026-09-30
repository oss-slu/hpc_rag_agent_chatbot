from fastapi.testclient import TestClient

from slu_hpc_rag.agent import build_agent
from slu_hpc_rag.api import create_app


class BrokenAgent:
    async def ainvoke(self, _):
        raise RuntimeError("secret internal detail")


def test_health():
    client = TestClient(create_app(agent=object()))
    body = client.get("/health").json()
    assert body["status"] == "ok"


def test_ask_returns_answer(scripted_model):
    agent = build_agent(scripted_model("Scratch is purged after 30 days."))
    client = TestClient(create_app(agent=agent))
    resp = client.post("/ask", json={"question": "How long does scratch last?"})
    assert resp.status_code == 200
    assert resp.json() == {"answer": "Scratch is purged after 30 days."}


def test_ask_rejects_empty_question():
    client = TestClient(create_app(agent=object()))
    assert client.post("/ask", json={"question": ""}).status_code == 422


def test_agent_failure_does_not_leak_details():
    client = TestClient(create_app(agent=BrokenAgent()))
    resp = client.post("/ask", json={"question": "hi"})
    assert resp.status_code == 502
    assert "secret" not in resp.text


def test_cors_is_off_unless_configured():
    client = TestClient(create_app(agent=object()))
    resp = client.options(
        "/ask",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in resp.headers


def test_cors_allows_configured_origin(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://hpc.slu.edu"]')
    client = TestClient(create_app(agent=object()))
    resp = client.options(
        "/ask",
        headers={"Origin": "https://hpc.slu.edu", "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers["access-control-allow-origin"] == "https://hpc.slu.edu"


def test_real_agent_is_built_lazily_on_first_question(monkeypatch, scripted_model):
    import slu_hpc_rag.api as api

    built = []

    def fake_build_model(settings):
        built.append(settings.chat_model)
        return scripted_model("ok")

    monkeypatch.setattr(api, "build_model", fake_build_model)
    client = TestClient(api.create_app())
    assert built == []  # starting the app needs no API key
    assert client.post("/ask", json={"question": "hi"}).json() == {"answer": "ok"}
    assert built == ["anthropic:claude-sonnet-5-5"]
