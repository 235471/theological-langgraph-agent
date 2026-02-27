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
- `0003_add_graph_run_traces_table`: adds `graph_run_traces` for LangSmith trace export metadata.

## Startup behavior

- Docker startup runs migrations via:
  - `alembic upgrade head && uvicorn ...`
- App startup does not run migrations anymore.
- For local (non-Docker) development, run migrations manually before starting the API:

```bash
alembic upgrade head
```
