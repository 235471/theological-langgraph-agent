# Database Migrations (Alembic)

This project now uses Alembic for schema versioning while keeping psycopg + SQL services.

## Prerequisites

- `DB_URL` must be set
- Install dependencies (`requirements-api.txt` or `requirements.txt`)

## Fresh database

```bash
alembic upgrade head
```

## Existing database (already created by legacy `init_db.py`)

1. Mark current schema as baseline:

```bash
alembic stamp 0001_baseline_init_schema
```

2. Apply new migrations:

```bash
alembic upgrade head
```

## Current revisions

- `0001_baseline_init_schema`: baseline schema equivalent to the original MVP tables/indexes.
- `0002_add_prompt_versions_jsonb`: adds `prompt_versions JSONB` to:
  - `analysis_runs`
  - `hitl_reviews`

## Startup behavior

- Docker startup runs: `alembic upgrade head && uvicorn ...`
- App startup also runs migrations via `run_migrations()`.
- Optional fallback to legacy bootstrap can be enabled with:
  - `DB_INIT_FALLBACK=true`
