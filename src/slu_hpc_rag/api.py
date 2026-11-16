"""HTTP interface."""

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, Field

from slu_hpc_rag import __version__
from slu_hpc_rag.agent import build_agent, build_model, message_text
from slu_hpc_rag.answers import AnswerRecord, AnswerStore, PostgresAnswerStore
from slu_hpc_rag.config import get_settings

log = logging.getLogger(__name__)

UNAVAILABLE = "The assistant is unavailable."
SEARCH_TOOL = "search_docs"


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class Feedback(BaseModel):
    answer_id: UUID
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=2000)


# Server-sent events in the format agreed in #5. Swap for the stream.py
# helpers when #5 is merged.
def _event(**fields: Any) -> str:
    return f"data: {json.dumps(fields)}\n\n"


def _token(text: str) -> str:
    return _event(type="token", text=text)


def _done(answer_id: UUID, sources: list[dict[str, str]]) -> str:
    return _event(type="done", answer_id=str(answer_id), sources=sources, findings=[])


def _error() -> str:
    return _event(type="error", message=UNAVAILABLE)


class _Run:
    """What the agent did while answering: the final text, tool calls and cited sources."""

    def __init__(self) -> None:
        self.answer = ""
        self.tool_calls: list[dict[str, Any]] = []
        self.sources: list[dict[str, str]] = []

    def add(self, message: Any) -> None:
        if isinstance(message, AIMessage):
            self.answer = message_text(message.content)
            self.tool_calls += [{"name": c["name"], "args": c["args"]} for c in message.tool_calls]
        elif isinstance(message, ToolMessage) and message.name == SEARCH_TOOL:
            seen = {s["url"] for s in self.sources}
            for hit in message.artifact or []:
                if hit["url"] not in seen:
                    seen.add(hit["url"])
                    self.sources.append({"title": hit["title"], "url": hit["url"]})


class _AnswerFilter:
    """Pass on only the model's final-answer text.

    Claude often writes a line ("Let me search the docs.") before a tool call
    in the same turn, and the stream doesn't reveal the tool call until that
    text has been sent. So the start of each model turn is held back: if a
    tool call arrives while the text is held, the text is dropped. Once a turn
    passes HOLD_CHARS, or ends without calling a tool, it is the answer.
    """

    HOLD_CHARS = 200

    def __init__(self) -> None:
        self._new_turn()

    def _new_turn(self) -> None:
        self.held = ""
        self.streaming = False
        self.calls_tools = False

    def chunk(self, chunk: Any, metadata: dict) -> str:
        """Text to send now for one streamed chunk (may be empty)."""
        if metadata.get("langgraph_node") != "model" or not isinstance(chunk, AIMessage):
            return ""  # tool output, or another node's messages
        if chunk.tool_calls or getattr(chunk, "tool_call_chunks", None):
            self.calls_tools = True
            self.held = ""
        text = "" if self.calls_tools else message_text(chunk.content)
        if self.streaming:
            return text
        self.held += text
        if len(self.held) < self.HOLD_CHARS:
            return ""
        self.streaming = True
        text, self.held = self.held, ""
        return text

    def turn_ended(self, message: AIMessage) -> str:
        """Text still held when a model turn finishes; it was the answer if no tool was called."""
        text = "" if message.tool_calls else self.held
        self._new_turn()
        return text


def create_app(agent=None, store: AnswerStore | None = None) -> FastAPI:
    """Build the app. Tests pass fakes; production builds the real agent lazily."""
    settings = get_settings()
    app = FastAPI(title="SLU HPC Assistant", version=__version__)
    answers = store or PostgresAnswerStore(settings.database_url)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    state = {"agent": agent}

    def get_agent():
        if state["agent"] is None:
            state["agent"] = build_agent(build_model(settings))
        return state["agent"]

    async def answer_events(question: str) -> AsyncIterator[str]:
        started = time.perf_counter()
        run, answer = _Run(), _AnswerFilter()
        try:
            stream = get_agent().astream(
                {"messages": [{"role": "user", "content": question}]},
                stream_mode=["messages", "updates"],
            )
            async for mode, data in stream:
                texts: list[str] = []
                if mode == "messages":
                    texts.append(answer.chunk(*data))
                else:
                    for node, update in data.items():
                        for message in (update or {}).get("messages", []):
                            run.add(message)
                            if node == "model" and isinstance(message, AIMessage):
                                texts.append(answer.turn_ended(message))
                for text in texts:
                    if text:
                        yield _token(text)
            answer_id = await answers.save(
                AnswerRecord(
                    question=question,
                    answer=run.answer,
                    model=settings.chat_model,
                    latency_ms=round((time.perf_counter() - started) * 1000),
                    sources=run.sources,
                    tool_calls=run.tool_calls,
                )
            )
        except Exception:
            log.exception("answering failed")
            yield _error()
            return
        yield _done(answer_id, run.sources)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/ask", response_class=StreamingResponse)
    async def ask(body: Question) -> StreamingResponse:
        return StreamingResponse(
            answer_events(body.question),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/feedback", status_code=204)
    async def feedback(body: Feedback) -> Response:
        if not await answers.rate(body.answer_id, body.rating, body.comment):
            raise HTTPException(status_code=404, detail="Unknown answer.")
        return Response(status_code=204)

    return app
