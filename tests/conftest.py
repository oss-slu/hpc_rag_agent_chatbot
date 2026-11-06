import json
import os
import re
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.messages.tool import tool_call_chunk
from langchain_core.outputs import ChatGenerationChunk

from slu_hpc_rag.answers import AnswerRecord, Rating
from slu_hpc_rag.config import get_settings


class MemoryAnswerStore:
    """In-memory AnswerStore for tests that don't need a database."""

    def __init__(self) -> None:
        self.answers: dict[UUID, AnswerRecord] = {}
        self.ratings: dict[UUID, tuple[Rating, str | None]] = {}

    async def save(self, record: AnswerRecord) -> UUID:
        answer_id = uuid4()
        self.answers[answer_id] = replace(record)
        return answer_id

    async def rate(self, answer_id: UUID, rating: Rating, comment: str | None = None) -> bool:
        if answer_id not in self.answers:
            return False
        self.ratings[answer_id] = (rating, comment)
        return True


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def database_url():
    """A freshly emptied test database; skips the test if none is configured."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    return url


class ScriptedModel(GenericFakeChatModel):
    """Offline stand-in for a chat model that replies from a fixed script.

    Streams like the real providers: string content word by word (vLLM),
    list content one block at a time (Claude), then any tool calls.
    """

    def bind_tools(self, tools, **kwargs):
        return self

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        reply = self._generate(messages, stop=stop, **kwargs).generations[0].message
        if isinstance(reply.content, str):
            pieces = [p for p in re.split(r"(\s)", reply.content) if p]
        else:
            pieces = [[block] for block in reply.content]
        for piece in pieces:
            yield ChatGenerationChunk(message=AIMessageChunk(content=piece, id=reply.id))
        if reply.tool_calls:
            calls = [
                tool_call_chunk(name=c["name"], args=json.dumps(c["args"]), id=c["id"], index=i)
                for i, c in enumerate(reply.tool_calls)
            ]
            yield ChatGenerationChunk(
                message=AIMessageChunk(content="", id=reply.id, tool_call_chunks=calls)
            )


def calls_tool(name: str, **args) -> AIMessage:
    """A scripted reply that calls a tool."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}])


@pytest.fixture
def scripted_model():
    def make(*replies: str | AIMessage) -> ScriptedModel:
        script = (r if isinstance(r, AIMessage) else AIMessage(content=r) for r in replies)
        return ScriptedModel(messages=iter(script))

    return make


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """Keep tests independent of a developer's real .env and environment."""
    monkeypatch.chdir("/")
    for var in ("DATABASE_URL", "CHAT_MODEL", "CORS_ORIGINS", "TEMPERATURE"):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
