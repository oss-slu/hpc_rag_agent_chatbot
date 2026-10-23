"""Minimal forward-only SQL migrations.

Files in ``migrations/`` run in filename order, each in its own transaction,
and are recorded in ``schema_migrations`` so they are applied exactly once.
"""

import sys
from importlib import resources

import psycopg

from slu_hpc_rag.config import get_settings

_LEDGER = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    name       text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def migration_files() -> list[tuple[str, str]]:
    folder = resources.files("slu_hpc_rag") / "migrations"
    files = sorted(f for f in folder.iterdir() if f.name.endswith(".sql"))
    return [(f.name, f.read_text(encoding="utf-8")) for f in files]


def migrate(database_url: str) -> list[str]:
    """Apply pending migrations and return the names of those applied."""
    applied: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(_LEDGER)
        done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
        for name, sql in migration_files():
            if name in done:
                continue
            with conn.transaction():
                conn.execute(sql)
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (name,))
            applied.append(name)
    return applied


def main() -> None:
    applied = migrate(get_settings().database_url)
    print("\n".join(f"applied {n}" for n in applied) or "database is up to date")
    sys.exit(0)
