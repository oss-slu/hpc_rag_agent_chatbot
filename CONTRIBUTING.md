# Contributing

## Setup

```sh
git clone <this repo>
cd hpc_rag_agent_chatbot
make setup
make test
```

To run the database tests too, start Postgres with `make db`, then run
`make test-all`.

## Making a change

1. Open or pick an issue so work isn't duplicated.
2. Branch from `main`.
3. Keep the change focused; one concern per pull request.
4. Add or update tests. Coverage must stay at or above 80%.
5. Run `make check test` before pushing.
6. Open a pull request.

## Database changes

Add a new numbered file in `src/slu_hpc_rag/migrations/` (for example
`0002_add_feedback.sql`). Never edit a migration that has already been merged;
deployed databases have already run it.

## Ground rules

- Don't commit secrets, `.env` files, or copies of SLU documentation. The
  ingestion job fetches documentation at runtime.
- The assistant must never invent cluster details. Changes to prompts or
  retrieval should keep answers grounded and cited.
