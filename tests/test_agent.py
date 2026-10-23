from langchain_core.messages import AIMessage

from slu_hpc_rag.agent import SYSTEM_PROMPT, answer_text, build_agent, build_model
from slu_hpc_rag.config import Settings


def test_agent_answers_with_offline_model(scripted_model):
    agent = build_agent(scripted_model("Use sbatch to submit jobs."))
    result = agent.invoke({"messages": [{"role": "user", "content": "How do I submit?"}]})
    assert answer_text(result) == "Use sbatch to submit jobs."


def test_system_prompt_demands_citations_and_honesty():
    assert "Cite" in SYSTEM_PROMPT
    assert "Research Computing" in SYSTEM_PROMPT


def test_answer_text_handles_content_blocks():
    msg = AIMessage(content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])
    assert answer_text({"messages": [msg]}) == "ab"


def test_build_model_uses_configured_model():
    model = build_model(Settings(chat_model="anthropic:claude-haiku-4-5", anthropic_api_key="x"))
    assert "haiku" in model.model
    assert model.temperature == 0.0
