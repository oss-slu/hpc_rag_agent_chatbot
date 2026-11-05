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


def message_text(content: str | list) -> str:
    """Plain text of a message or chunk.

    vLLM sends content as a string; Claude sends a list of blocks, of which
    only the ``text`` blocks are answer text.
    """
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def answer_text(result: dict) -> str:
    """Pull the final answer out of an agent result as plain text."""
    return message_text(result["messages"][-1].content)
