import json
from uuid import UUID

import pytest

from slu_hpc_rag import stream
from slu_hpc_rag.contracts import Finding

SOURCES = [{"title": "Batch jobs", "url": "https://example.edu/batch"}]


def test_helpers_write_one_data_line_per_event():
    assert stream.token("Use ") == 'data: {"type": "token", "text": "Use "}\n\n'
    assert (
        stream.error() == 'data: {"type": "error", "message": "The assistant is unavailable."}\n\n'
    )
    answer_id = UUID("12345678-1234-5678-1234-567812345678")
    finding = Finding(severity="warning", rule="r", line=2, message="m")
    raw = stream.done(answer_id, SOURCES, [finding])
    assert raw.startswith("data: ") and raw.endswith("\n\n") and raw.count("\n") == 2
    assert json.loads(raw.removeprefix("data: ")) == {
        "type": "done",
        "answer_id": str(answer_id),
        "sources": SOURCES,
        "findings": [finding.model_dump()],
    }


def test_text_with_newlines_and_unicode_stays_on_one_data_line():
    raw = stream.token("line one\nline two ✓")
    assert raw.count("\n") == 2  # the newline inside the text is escaped
    assert list(stream.parse([raw])) == [{"type": "token", "text": "line one\nline two ✓"}]


def test_fake_stream_sends_tokens_then_exactly_one_done():
    events = list(stream.parse(stream.fake_stream()))
    types = [e["type"] for e in events]
    assert types.count("done") == 1 and types[-1] == "done"
    assert set(types[:-1]) == {"token"} and len(types) > 5
    assert "".join(e["text"] for e in events[:-1]) == stream.FAKE_ANSWER
    assert events[-1]["sources"] == stream.FAKE_SOURCES
    assert all(s["url"].startswith("https://example.edu/") for s in events[-1]["sources"])


def test_parser_handles_token_done_and_error_events():
    raw = stream.token("Hi") + stream.done("id-1", SOURCES) + stream.error()
    assert [e["type"] for e in stream.parse([raw])] == ["token", "done", "error"]


@pytest.mark.parametrize("cut", range(1, 40))
def test_parser_handles_an_event_split_across_reads(cut):
    raw = stream.token("Hello there") + stream.done("id-1", SOURCES)
    parser = stream.EventParser()
    events = parser.feed(raw[:cut]) + parser.feed(raw[cut:])
    assert [e["type"] for e in events] == ["token", "done"]
    assert events[0]["text"] == "Hello there"


def test_parser_waits_for_the_blank_line_and_ignores_other_fields():
    parser = stream.EventParser()
    assert parser.feed('data: {"type": "token", "text": "a"}\n') == []  # not finished yet
    assert parser.feed("\n") == [{"type": "token", "text": "a"}]
    assert parser.feed(": keep-alive\nevent: message\nid: 7\n\n") == []
    assert parser.feed('data:{"type": "error", "message": "x"}\r\n\r\n') == [
        {"type": "error", "message": "x"}
    ]
