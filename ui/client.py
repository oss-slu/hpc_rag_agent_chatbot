"""Talking to the API: stream an answer, send a rating.

Kept free of Streamlit so it can be unit-tested. Nothing here raises to the
caller for expected failures (API down, bad response); they become a friendly
message instead, and the details go to the log.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx

from slu_hpc_rag.stream import UNAVAILABLE, error, fake_stream, parse

log = logging.getLogger(__name__)

API_DOWN = "Can't reach the assistant right now. Please try again in a minute."
FEEDBACK_FAILED = "Couldn't save your rating. Please try again."

# Connecting should be quick; an answer can take a while between tokens.
TIMEOUT = httpx.Timeout(10.0, read=120.0)


@dataclass
class Answer:
    """What one question produced; filled in while the stream is read."""

    text: str = ""
    answer_id: str | None = None
    sources: list[dict[str, str]] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def finished(self) -> bool:
        return self.answer_id is not None or self.error is not None


class Client:
    def __init__(self, api_url: str, fake: bool = False, http: httpx.Client | None = None):
        self.api_url = api_url.rstrip("/")
        self.fake = fake
        self.http = http or httpx.Client(timeout=TIMEOUT)

    def ask(self, question: str, answer: Answer) -> Iterator[str]:
        """Yield the answer text piece by piece, filling in ``answer`` as it goes.

        Made for ``st.write_stream``: the yielded strings are shown as they
        arrive, and ``answer`` holds the sources or the error afterwards.
        """
        try:
            for event in parse(self._pieces(question)):
                kind = event.get("type")
                if kind == "token":
                    answer.text += event["text"]
                    yield event["text"]
                elif kind == "done":
                    answer.answer_id = event["answer_id"]
                    answer.sources = event.get("sources", [])
                    answer.findings = event.get("findings", [])
                    return
                elif kind == "error":
                    answer.error = event.get("message") or UNAVAILABLE
                    return
        except httpx.HTTPError as exc:
            log.warning("asking the API failed: %r", exc)
            answer.error = API_DOWN
            return
        except (ValueError, KeyError) as exc:  # malformed event
            log.warning("bad event from the API: %r", exc)
            answer.error = UNAVAILABLE
            return
        if not answer.finished:  # the stream stopped without done or error
            answer.error = UNAVAILABLE

    def rate(self, answer_id: str, rating: int, comment: str | None = None) -> str | None:
        """Send 👍 (1) or 👎 (-1). Returns an error message, or None if it was saved."""
        if self.fake:
            return None
        body = {"answer_id": answer_id, "rating": rating}
        if comment:
            body["comment"] = comment
        try:
            resp = self.http.post(f"{self.api_url}/feedback", json=body)
        except httpx.HTTPError as exc:
            log.warning("sending feedback failed: %r", exc)
            return FEEDBACK_FAILED
        if resp.status_code != 204:
            log.warning("feedback returned %s: %s", resp.status_code, resp.text[:200])
            return FEEDBACK_FAILED
        return None

    def _pieces(self, question: str) -> Iterator[str]:
        if self.fake:
            yield from fake_stream(delay=0.03)
            return
        with self.http.stream("POST", f"{self.api_url}/ask", json={"question": question}) as resp:
            if resp.status_code != 200:
                log.warning("/ask returned %s", resp.status_code)
                yield error()  # shown as the friendly error; details are in the log
                return
            yield from resp.iter_text()
