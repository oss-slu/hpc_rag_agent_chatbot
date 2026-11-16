from uuid import UUID, uuid4

import psycopg
import pytest
from conftest import MemoryAnswerStore

from slu_hpc_rag import db
from slu_hpc_rag.answers import AnswerRecord, PostgresAnswerStore

pytestmark = pytest.mark.anyio

RECORD = AnswerRecord(
    question="How do I submit a job?",
    answer="Use sbatch [1].",
    model="fake:model",
    latency_ms=1234,
    sources=[{"title": "Batch jobs", "url": "https://example.edu/batch"}],
    tool_calls=[{"name": "search_docs", "args": {"query": "submit job"}}],
)


@pytest.fixture
def pg_store(database_url):
    db.migrate(database_url)
    return PostgresAnswerStore(database_url)


@pytest.fixture(params=["memory", pytest.param("postgres", marks=pytest.mark.db)])
def store(request):
    if request.param == "memory":
        return MemoryAnswerStore()
    return request.getfixturevalue("pg_store")


# Contract tests: the in-memory fake used by the API tests must behave like Postgres.


async def test_save_returns_a_new_id_each_time(store):
    first, second = await store.save(RECORD), await store.save(RECORD)
    assert isinstance(first, UUID)
    assert first != second


async def test_rate_known_answer(store):
    answer_id = await store.save(RECORD)
    assert await store.rate(answer_id, -1, "wrong partition")
    assert await store.rate(answer_id, 1)  # rating again overwrites


async def test_rate_unknown_answer(store):
    assert not await store.rate(uuid4(), 1)


# Postgres only.


def fetch(url, answer_id, columns):
    with psycopg.connect(url) as conn:
        sql = f"SELECT {columns} FROM answers WHERE id = %s"
        return conn.execute(sql, (answer_id,)).fetchone()


@pytest.mark.db
async def test_save_stores_every_field(pg_store, database_url):
    answer_id = await pg_store.save(RECORD)
    row = fetch(
        database_url,
        answer_id,
        "question, answer, sources, tool_calls, model, latency_ms, rating, created_at",
    )
    *stored, rating, created_at = row
    assert stored == [
        RECORD.question,
        RECORD.answer,
        RECORD.sources,
        RECORD.tool_calls,
        RECORD.model,
        RECORD.latency_ms,
    ]
    assert rating is None
    assert created_at is not None


@pytest.mark.db
async def test_rating_is_stored_and_overwritten(pg_store, database_url):
    answer_id = await pg_store.save(RECORD)
    await pg_store.rate(answer_id, -1, "wrong partition")
    assert fetch(database_url, answer_id, "rating, comment") == (-1, "wrong partition")

    await pg_store.rate(answer_id, 1)
    rating, comment, rated_at = fetch(database_url, answer_id, "rating, comment, rated_at")
    assert (rating, comment) == (1, None)
    assert rated_at is not None


@pytest.mark.db
async def test_database_rejects_other_ratings(pg_store):
    answer_id = await pg_store.save(RECORD)
    with pytest.raises(psycopg.errors.CheckViolation):
        await pg_store.rate(answer_id, 0)  # type: ignore[arg-type]


@pytest.mark.db
def test_log_has_no_user_or_network_columns(pg_store, database_url):
    with psycopg.connect(database_url) as conn:
        columns = {
            name
            for (name,) in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'answers'"
            )
        }
    assert columns == {
        "id",
        "created_at",
        "question",
        "answer",
        "sources",
        "tool_calls",
        "model",
        "latency_ms",
        "rating",
        "comment",
        "rated_at",
    }
