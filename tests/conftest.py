import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from slu_hpc_rag.config import get_settings


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
