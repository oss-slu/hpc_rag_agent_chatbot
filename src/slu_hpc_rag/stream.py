"""The server-sent events that ``/ask`` streams, and a parser for them.

Each event is one ``data: <json>`` line followed by a blank line:

    data: {"type": "token", "text": "Use "}
    data: {"type": "done", "answer_id": "...", "sources": [{"title", "url"}], "findings": []}
    data: {"type": "error", "message": "The assistant is unavailable."}

``token`` events come while the answer is written. A stream ends with exactly
one ``done``, or with one ``error`` instead.

This module uses only the standard library and ``contracts``, so the UI can
import it without the rest of the backend.
"""

import json
import time
from collections.abc import Iterable, Iterator, Sequence
from typing import Any
from uuid import UUID

from slu_hpc_rag.contracts import Finding

UNAVAILABLE = "The assistant is unavailable."


def event(**fields: Any) -> str:
    """One server-sent event carrying ``fields`` as JSON."""
    return f"data: {json.dumps(fields, ensure_ascii=False)}\n\n"


def token(text: str) -> str:
    return event(type="token", text=text)


def done(
    answer_id: UUID | str,
    sources: Sequence[dict[str, str]],
    findings: Sequence[Finding] = (),
) -> str:
    return event(
        type="done",
        answer_id=str(answer_id),
        sources=list(sources),
        findings=[f.model_dump() for f in findings],
    )


def error(message: str = UNAVAILABLE) -> str:
    return event(type="error", message=message)


class EventParser:
    """Turn streamed text into events, however the network splits it.

    Feed it each piece of text as it arrives; it returns the events that are
    now complete. Lines other than ``data:`` (comments, ``event:``, ``id:``)
    are ignored, as server-sent events allow.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._data: list[str] = []

    def feed(self, text: str) -> list[dict[str, Any]]:
        self._buffer += text.replace("\r\n", "\n")
        events = []
        *lines, self._buffer = self._buffer.split("\n")
        for line in lines:
            if line == "":
                if self._data:
                    events.append(json.loads("\n".join(self._data)))
                    self._data = []
            elif line.startswith("data:"):
                self._data.append(line.removeprefix("data:").removeprefix(" "))
        return events


def parse(pieces: Iterable[str]) -> Iterator[dict[str, Any]]:
    """Events from an iterable of text pieces (for example ``httpx``'s ``iter_text``)."""
    parser = EventParser()
    for piece in pieces:
        yield from parser.feed(piece)


FAKE_ANSWER = (
    "This is a made-up answer from the fake stream. Submit batch jobs with "
    "`sbatch job.sh` [1], and check on them with `squeue --me` [2]."
)
FAKE_SOURCES = [
    {"title": "Batch jobs (example)", "url": "https://example.edu/how-to/batch-jobs/"},
    {"title": "Monitoring jobs (example)", "url": "https://example.edu/how-to/monitor-jobs/"},
]


def fake_stream(
    text: str = FAKE_ANSWER,
    sources: Sequence[dict[str, str]] = tuple(FAKE_SOURCES),
    delay: float = 0.0,
) -> Iterator[str]:
    """A made-up ``/ask`` stream: ``text`` word by word, then ``done``.

    For building and testing the UI without the API. ``delay`` is the pause
    between tokens in seconds.
    """
    words = text.split(" ")
    for i, word in enumerate(words):
        if delay:
            time.sleep(delay)
        yield token(word if i == len(words) - 1 else word + " ")
    yield done("00000000-0000-0000-0000-000000000000", sources)
