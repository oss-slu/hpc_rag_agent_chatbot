"""The conversation log: every answer given, and the user's rating of it.

The store's methods are async, but use psycopg's synchronous driver in a
worker thread. Psycopg's async mode can't run on Windows' default
ProactorEventLoop, which uvicorn --reload and the test client both use.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from uuid import UUID

import anyio
import psycopg
from psycopg.types.json import Jsonb

Rating = Literal[-1, 1]


@dataclass(frozen=True)
class AnswerRecord:
    question: str
    answer: str
    model: str
    latency_ms: int
    sources: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class AnswerStore(Protocol):
    async def save(self, record: AnswerRecord) -> UUID:
        """Store an answer and return its new id."""
        ...

    async def rate(self, answer_id: UUID, rating: Rating, comment: str | None = None) -> bool:
        """Record a rating; False if no answer has this id. Rating again overwrites."""
        ...


_INSERT = """
INSERT INTO answers (question, answer, sources, tool_calls, model, latency_ms)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING id
"""

_RATE = """
UPDATE answers SET rating = %s, comment = %s, rated_at = now()
WHERE id = %s
"""


class PostgresAnswerStore:
    """Opens one connection per call, which is plenty for a laptop or a small pilot."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    async def save(self, record: AnswerRecord) -> UUID:
        return await anyio.to_thread.run_sync(self._save, record)

    async def rate(self, answer_id: UUID, rating: Rating, comment: str | None = None) -> bool:
        return await anyio.to_thread.run_sync(self._rate, answer_id, rating, comment)

    def _save(self, r: AnswerRecord) -> UUID:
        with psycopg.connect(self.database_url) as conn:
            params = (r.question, r.answer, Jsonb(r.sources), Jsonb(r.tool_calls))
            row = conn.execute(_INSERT, (*params, r.model, r.latency_ms)).fetchone()
        assert row is not None
        return row[0]

    def _rate(self, answer_id: UUID, rating: Rating, comment: str | None) -> bool:
        with psycopg.connect(self.database_url) as conn:
            cur = conn.execute(_RATE, (rating, comment, answer_id))
            return cur.rowcount == 1
