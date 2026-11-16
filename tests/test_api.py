import json
from uuid import UUID, uuid4

import anyio
import psycopg
import pytest
from conftest import MemoryAnswerStore, ScriptedModel, calls_tool
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from slu_hpc_rag import db
from slu_hpc_rag.agent import build_agent
from slu_hpc_rag.answers import AnswerRecord, PostgresAnswerStore
from slu_hpc_rag.api import create_app

BATCH = {"title": "Batch jobs", "url": "https://example.edu/batch"}
GPU = {"title": "GPU jobs", "url": "https://example.edu/gpu"}


@tool(response_format="content_and_artifact")
def search_docs(query: str):
    """Search the documentation."""
    return "[1] Batch jobs\n[2] GPU jobs", [BATCH, GPU, BATCH]


class BrokenAgent:
    def astream(self, *args, **kwargs):
        raise RuntimeError("secret internal detail")


class BrokenStore(MemoryAnswerStore):
    async def save(self, record):
        raise RuntimeError("secret database detail")


def events(resp) -> list[dict]:
    return [json.loads(line[len("data: ") :]) for line in resp.iter_lines() if line]


def ask(client, question="How do I submit a job?"):
    with client.stream("POST", "/ask", json={"question": question}) as resp:
        return resp, events(resp)


def app_with(*replies: str | AIMessage, store=None) -> TestClient:
    """An app whose agent replies from a script and can call the fake search_docs."""
    script = (r if isinstance(r, AIMessage) else AIMessage(content=r) for r in replies)
    agent = build_agent(ScriptedModel(messages=iter(script)), [search_docs])
    return TestClient(create_app(agent=agent, store=store or MemoryAnswerStore()))


def test_health():
    client = TestClient(create_app(agent=object()))
    body = client.get("/health").json()
    assert body["status"] == "ok"


LONG = "Submit batch jobs with sbatch [1]. " + "Request only the time and memory you need. " * 8
SHORT = "Use sbatch [1]."


def test_ask_streams_tokens_then_done():
    store = MemoryAnswerStore()
    client = app_with(calls_tool("search_docs", query="submit"), LONG, store=store)
    resp, evs = ask(client)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    types = [e["type"] for e in evs]
    assert types.count("token") > 10  # streamed, not sent in one piece
    assert types[-1] == "done" and types.count("done") == 1
    assert "".join(e["text"] for e in evs if e["type"] == "token") == LONG

    done = evs[-1]
    assert done["sources"] == [BATCH, GPU]  # de-duplicated, in order
    assert done["findings"] == []

    saved = store.answers[UUID(done["answer_id"])]
    assert saved.question == "How do I submit a job?"
    assert saved.answer == LONG
    assert saved.sources == [BATCH, GPU]
    assert saved.tool_calls == [{"name": "search_docs", "args": {"query": "submit"}}]
    assert saved.model == "anthropic:claude-sonnet-5-5"
    assert saved.latency_ms >= 0


def test_short_answer_arrives_whole():
    _, evs = ask(app_with(SHORT))
    assert evs[0] == {"type": "token", "text": SHORT}
    assert evs[-1]["type"] == "done"


def test_ask_streams_claude_style_content_blocks():
    blocks = [{"type": "thinking", "thinking": "hidden"}]
    blocks += [{"type": "text", "text": word} for word in LONG.split(" ")]
    _, evs = ask(app_with(AIMessage(content=blocks)))
    tokens = [e["text"] for e in evs if e["type"] == "token"]
    assert len(tokens) > 10
    assert "".join(tokens) == "".join(LONG.split(" "))
    assert "hidden" not in json.dumps(evs)


def test_text_before_a_tool_call_is_not_streamed():
    preamble = AIMessage(
        content=[
            {"type": "text", "text": "Let me search the docs."},
            {"type": "tool_use", "id": "c1", "name": "search_docs", "input": {"query": "q"}},
        ],
        tool_calls=[{"name": "search_docs", "args": {"query": "q"}, "id": "c1"}],
    )
    store = MemoryAnswerStore()
    _, evs = ask(app_with(preamble, LONG, store=store))
    assert "".join(e["text"] for e in evs if e["type"] == "token") == LONG
    assert store.answers[UUID(evs[-1]["answer_id"])].answer == LONG


def test_ask_rejects_empty_question():
    client = TestClient(create_app(agent=object()))
    assert client.post("/ask", json={"question": ""}).status_code == 422


@pytest.mark.parametrize(
    "client",
    [
        lambda: TestClient(create_app(agent=BrokenAgent(), store=MemoryAnswerStore())),
        lambda: app_with("Use sbatch.", store=BrokenStore()),
    ],
    ids=["agent-fails", "store-fails"],
)
def test_failure_sends_error_event_without_details(client, caplog):
    resp, evs = ask(client())
    assert resp.status_code == 200  # the stream has already started
    assert evs[-1] == {"type": "error", "message": "The assistant is unavailable."}
    assert "done" not in [e["type"] for e in evs]
    assert "secret" not in json.dumps(evs)
    assert "secret" in caplog.text  # details go to the log only


def test_feedback_rates_a_known_answer():
    store = MemoryAnswerStore()
    answer_id = anyio.run(
        store.save, AnswerRecord(question="q", answer="a", model="m", latency_ms=1)
    )
    client = TestClient(create_app(agent=object(), store=store))

    resp = client.post(
        "/feedback", json={"answer_id": str(answer_id), "rating": -1, "comment": "wrong"}
    )
    assert resp.status_code == 204
    assert resp.content == b""
    assert store.ratings[answer_id] == (-1, "wrong")


def test_feedback_unknown_answer_is_404():
    client = TestClient(create_app(agent=object(), store=MemoryAnswerStore()))
    resp = client.post("/feedback", json={"answer_id": str(uuid4()), "rating": 1})
    assert resp.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"answer_id": str(uuid4()), "rating": 0},
        {"answer_id": str(uuid4()), "rating": 5},
        {"answer_id": str(uuid4()), "rating": "1"},
        {"answer_id": "not-a-uuid", "rating": 1},
        {"answer_id": str(uuid4()), "rating": 1, "comment": "x" * 2001},
    ],
)
def test_feedback_rejects_invalid_input(body):
    client = TestClient(create_app(agent=object(), store=MemoryAnswerStore()))
    assert client.post("/feedback", json=body).status_code == 422


@pytest.mark.db
def test_ask_then_thumbs_down_end_to_end(database_url):
    db.migrate(database_url)
    client = app_with("Use sbatch.", store=PostgresAnswerStore(database_url))
    _, evs = ask(client)
    answer_id = evs[-1]["answer_id"]

    resp = client.post("/feedback", json={"answer_id": answer_id, "rating": -1})
    assert resp.status_code == 204
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "SELECT question, answer, rating FROM answers WHERE id = %s", (answer_id,)
        ).fetchone()
    assert row == ("How do I submit a job?", "Use sbatch.", -1)


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
    client = TestClient(api.create_app(store=MemoryAnswerStore()))
    assert built == []  # starting the app needs no API key
    _, evs = ask(client, "hi")
    assert [e["type"] for e in evs] == ["token", "done"]
    assert built == ["anthropic:claude-sonnet-5-5"]
