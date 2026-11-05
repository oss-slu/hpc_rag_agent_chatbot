import os
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

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
    """Offline stand-in for a chat model that replies from a fixed script."""

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture
def scripted_model():
    def make(*replies: str) -> ScriptedModel:
        return ScriptedModel(messages=iter(AIMessage(content=r) for r in replies))

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
