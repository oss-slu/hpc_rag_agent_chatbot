import json

import httpx
import pytest

from slu_hpc_rag import stream
from ui.client import API_DOWN, FEEDBACK_FAILED, Answer, Client

SOURCES = [{"title": "Batch jobs", "url": "https://example.edu/batch"}]
GOOD = stream.token("Use ") + stream.token("sbatch.") + stream.done("id-1", SOURCES)


def client(handler) -> Client:
    return Client("http://api.test/", http=httpx.Client(transport=httpx.MockTransport(handler)))


def sse(body: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=body, headers={"content-type": "text/event-stream"})


def ask(c: Client, question: str = "q") -> tuple[list[str], Answer]:
    answer = Answer()
    return list(c.ask(question, answer)), answer


def test_streams_tokens_then_records_sources():
    seen = {}

    def handler(request):
        seen["url"], seen["body"] = str(request.url), json.loads(request.content)
        return sse(GOOD)

    pieces, answer = ask(client(handler), "How do I submit a job?")
    assert pieces == ["Use ", "sbatch."]
    assert (answer.text, answer.answer_id, answer.sources) == ("Use sbatch.", "id-1", SOURCES)
    assert answer.error is None
    assert seen == {"url": "http://api.test/ask", "body": {"question": "How do I submit a job?"}}


def test_error_event_becomes_the_message():
    _, answer = ask(client(lambda r: sse(stream.token("Use ") + stream.error())))
    assert answer.error == stream.UNAVAILABLE and answer.answer_id is None


def test_api_down_is_a_friendly_error():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    pieces, answer = ask(client(handler))
    assert pieces == [] and answer.error == API_DOWN
    assert "refused" not in answer.error


@pytest.mark.parametrize("status", [422, 500, 502])
def test_bad_status_is_a_friendly_error(status):
    _, answer = ask(client(lambda r: httpx.Response(status, text="secret stack trace")))
    assert answer.error == stream.UNAVAILABLE


@pytest.mark.parametrize(
    "body", [stream.token("cut off"), "data: {not json}\n\n", 'data: {"type": "token"}\n\n']
)
def test_truncated_or_malformed_stream_is_an_error(body):
    _, answer = ask(client(lambda r: sse(body)))
    assert answer.error == stream.UNAVAILABLE


def test_fake_mode_needs_no_api():
    def handler(request):
        raise AssertionError("fake mode must not call the API")

    c = Client(
        "http://api.test", fake=True, http=httpx.Client(transport=httpx.MockTransport(handler))
    )
    pieces, answer = ask(c)
    assert "".join(pieces) == stream.FAKE_ANSWER
    assert answer.sources == stream.FAKE_SOURCES and answer.answer_id
    assert c.rate(answer.answer_id, -1) is None


def test_rate_posts_feedback():
    seen = {}

    def handler(request):
        seen["url"], seen["body"] = str(request.url), json.loads(request.content)
        return httpx.Response(204)

    assert client(handler).rate("id-1", -1, "wrong partition") is None
    assert seen == {
        "url": "http://api.test/feedback",
        "body": {"answer_id": "id-1", "rating": -1, "comment": "wrong partition"},
    }


@pytest.mark.parametrize("status", [404, 422, 500])
def test_rate_failure_is_reported(status):
    assert client(lambda r: httpx.Response(status)).rate("id-1", 1) == FEEDBACK_FAILED


def test_rate_with_api_down_is_reported():
    def handler(request):
        raise httpx.ConnectError("down")

    assert client(handler).rate("id-1", 1) == FEEDBACK_FAILED
