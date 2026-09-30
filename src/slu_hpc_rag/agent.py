"""The question-answering agent.

Retrieval tools arrive in a later PR. For now the agent is wired up with
no tools so the API, tests and deployment can be built around it.
"""

from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from slu_hpc_rag.config import Settings

SYSTEM_PROMPT = """\
You help researchers at Saint Louis University use the university's \
high-performance computing cluster.

Rules:
- Answer only from the documentation you are given through your tools.
- Cite the documentation URL for every factual claim.
- If the documentation does not answer the question, say so plainly and \
suggest contacting SLU Research Computing. Never guess partition names, \
limits, paths or commands.
"""


def build_model(settings: Settings) -> BaseChatModel:
    return init_chat_model(settings.chat_model, temperature=settings.temperature)


def build_agent(model: BaseChatModel, tools: Sequence[BaseTool] = ()):
    return create_agent(model=model, tools=list(tools), system_prompt=SYSTEM_PROMPT)


def answer_text(result: dict) -> str:
    """Pull the final answer out of an agent result as plain text."""
    content = result["messages"][-1].content
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))
