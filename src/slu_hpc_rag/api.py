"""HTTP interface."""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from slu_hpc_rag import __version__
from slu_hpc_rag.agent import answer_text, build_agent, build_model
from slu_hpc_rag.config import get_settings

log = logging.getLogger(__name__)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class Answer(BaseModel):
    answer: str


def create_app(agent=None) -> FastAPI:
    """Build the app. Tests pass a fake agent; production builds the real one lazily."""
    settings = get_settings()
    app = FastAPI(title="SLU HPC Assistant", version=__version__)

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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/ask", response_model=Answer)
    async def ask(body: Question) -> Answer:
        try:
            result = await get_agent().ainvoke(
                {"messages": [{"role": "user", "content": body.question}]}
            )
        except Exception:
            log.exception("agent failed")
            raise HTTPException(status_code=502, detail="The assistant is unavailable.") from None
        return Answer(answer=answer_text(result))

    return app
