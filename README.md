# slu-hpc-rag

An assistant that answers questions about Saint Louis University's HPC cluster
using the cluster's official documentation, and cites the page it got each
answer from.

> **Status:** early scaffolding. The API runs, but the assistant has no
> retrieval tools yet, so it can't answer from the documentation. Ingestion
> and retrieval are coming in follow-up pull requests.

## How it works

1. **Ingest.** A job fetches the SLU documentation page, splits it into
   sections, embeds them, and stores them in Postgres with pgvector. The page's
   URL changes with every update, so documents are keyed by a fixed name and
   the job re-indexes only when the content actually changes.
2. **Retrieve.** Questions are matched against the stored sections using both
   vector similarity and Postgres full-text search, which catches exact terms
   like partition names and `sbatch` flags.
3. **Answer.** A Claude model answers from the retrieved sections only, cites
   their URLs, and says so when the docs don't cover a question.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and Docker.

```sh
make setup      # install dependencies
make test       # run unit tests (no API key or database needed)

make db         # start Postgres + pgvector
make migrate    # create the tables
cp .env.example .env   # add your ANTHROPIC_API_KEY
make serve      # http://localhost:8000/docs
```

Run `make` on its own to see every command.

## API

| Method | Path      | Purpose                                  |
|--------|-----------|------------------------------------------|
| GET    | `/health` | Liveness check                           |
| POST   | `/ask`    | `{"question": "..."}` → `{"answer": "..."}` |

## Configuration

Settings come from environment variables or `.env`. See
[`.env.example`](.env.example).

| Variable            | Default                          |
|---------------------|----------------------------------|
| `ANTHROPIC_API_KEY` | none (required to answer questions) |
| `DATABASE_URL`      | `postgresql://hpc:hpc@localhost:5432/hpc_rag` |
| `CHAT_MODEL`        | `anthropic:claude-sonnet-5-5`    |
| `CORS_ORIGINS`      | none (CORS disabled)             |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
