import os

import pytest

from slu_hpc_rag import db


def test_migrations_are_ordered_and_named():
    names = [name for name, _ in db.migration_files()]
    assert names == sorted(names)
    assert names[0] == "0001_documents.sql"


@pytest.fixture
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    import psycopg

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    return url


@pytest.mark.db
def test_migrate_is_idempotent(database_url):
    assert db.migrate(database_url) == ["0001_documents.sql"]
    assert db.migrate(database_url) == []


@pytest.mark.db
def test_schema_supports_hybrid_search(database_url):
    import psycopg

    db.migrate(database_url)
    vec = "[" + ",".join(["0.1"] * 1024) + "]"
    with psycopg.connect(database_url) as conn:
        conn.execute(
            "INSERT INTO documents (slug, entry_url) VALUES ('guide', 'https://example.edu')"
        )
        conn.execute(
            "INSERT INTO chunks (doc_slug, source_url, ordinal, body, embedding)"
            " VALUES ('guide', 'https://example.edu/v2', 0,"
            " 'Submit GPU jobs with sbatch --gres', %s::vector)",
            (vec,),
        )
        by_vector = conn.execute(
            "SELECT source_url FROM chunks ORDER BY embedding <=> %s::vector LIMIT 1", (vec,)
        ).fetchone()
        by_text = conn.execute(
            "SELECT count(*) FROM chunks WHERE body_tsv @@ plainto_tsquery('english', 'gpu jobs')"
        ).fetchone()
        conn.execute("DELETE FROM documents WHERE slug = 'guide'")
        remaining = conn.execute("SELECT count(*) FROM chunks").fetchone()
    assert by_vector == ("https://example.edu/v2",)
    assert by_text == (1,)
    assert remaining == (0,)  # chunks go away with their document


@pytest.mark.db
def test_cli_reports_status(database_url, monkeypatch, capsys):
    from slu_hpc_rag.config import get_settings

    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    with pytest.raises(SystemExit):
        db.main()
    assert "applied 0001_documents.sql" in capsys.readouterr().out
