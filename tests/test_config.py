from slu_hpc_rag.config import get_settings


def test_defaults_are_safe():
    s = get_settings()
    assert s.temperature == 0.0
    assert s.cors_origins == []


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("CHAT_MODEL", "anthropic:claude-haiku-4-5")
    assert get_settings().chat_model == "anthropic:claude-haiku-4-5"
