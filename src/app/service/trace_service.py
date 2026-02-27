"""
Trace Service

Exports full LangSmith graph traces to Supabase Storage and persists
trace metadata/status in PostgreSQL.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from app.database.connection import get_connection
from app.utils.logger import get_logger

try:
    from langsmith import Client as LangSmithClient
except ImportError:  # pragma: no cover
    LangSmithClient = None

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None

try:
    from langchain_core.tracers.langchain import wait_for_all_tracers
except ImportError:  # pragma: no cover
    wait_for_all_tracers = None

logger = get_logger(__name__)

_ls_client: LangSmithClient | None = None
_supabase_client = None
READ_RUN_RETRY_ATTEMPTS = 4
READ_RUN_RETRY_DELAY_SECONDS = 2


def _is_tracing_enabled() -> bool:
    return os.getenv("LANGCHAIN_TRACING_V2", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _get_langsmith_client() -> LangSmithClient | None:
    global _ls_client
    if LangSmithClient is None:
        return None
    if _ls_client is None:
        _ls_client = LangSmithClient()
    return _ls_client


def _get_supabase_client():
    global _supabase_client
    if create_client is None:
        return None

    project_url = os.getenv("SUPABASE_PROJECT")
    secret_key = os.getenv("SUPABASE_SECRET_KEY")
    if not project_url or not secret_key:
        return None

    if _supabase_client is None:
        _supabase_client = create_client(project_url, secret_key)
    return _supabase_client


def _serialize_run(run: Any) -> bytes:
    if hasattr(run, "model_dump"):
        payload = run.model_dump()
    elif hasattr(run, "dict"):
        payload = run.dict()
    else:
        payload = run
    return json.dumps(payload, default=str).encode("utf-8")


def _read_langsmith_run_with_retry(
    ls_client: LangSmithClient, langsmith_run_id: str
):
    if wait_for_all_tracers:
        try:
            wait_for_all_tracers()
        except Exception as flush_err:
            logger.warning(
                f"LangSmith tracer flush failed before read_run: {flush_err}",
                extra={
                    "event": "trace_export_flush_failed",
                    "langsmith_run_id": langsmith_run_id,
                },
            )

    last_err: Exception | None = None
    for attempt in range(1, READ_RUN_RETRY_ATTEMPTS + 1):
        try:
            return ls_client.read_run(langsmith_run_id, load_child_runs=True)
        except Exception as err:
            last_err = err
            if attempt < READ_RUN_RETRY_ATTEMPTS:
                logger.info(
                    "LangSmith run not yet available; retrying read_run",
                    extra={
                        "event": "trace_export_read_retry",
                        "langsmith_run_id": langsmith_run_id,
                        "attempt": attempt,
                        "max_attempts": READ_RUN_RETRY_ATTEMPTS,
                        "sleep_seconds": READ_RUN_RETRY_DELAY_SECONDS,
                    },
                )
                time.sleep(READ_RUN_RETRY_DELAY_SECONDS)

    raise RuntimeError(
        f"LangSmith run not found after {READ_RUN_RETRY_ATTEMPTS} attempts: "
        f"{last_err}"
    )


def _upsert_trace_status(
    run_id: str,
    langsmith_run_id: str | None,
    status: str,
    storage_path: str | None = None,
    size_bytes: int | None = None,
    error_message: str | None = None,
) -> None:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO graph_run_traces (
                        run_id, langsmith_run_id, storage_path, size_bytes, status, error_message
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (run_id) DO UPDATE SET
                        langsmith_run_id = EXCLUDED.langsmith_run_id,
                        storage_path = EXCLUDED.storage_path,
                        size_bytes = EXCLUDED.size_bytes,
                        status = EXCLUDED.status,
                        error_message = EXCLUDED.error_message
                    """,
                    (
                        run_id,
                        langsmith_run_id,
                        storage_path,
                        size_bytes,
                        status,
                        error_message,
                    ),
                )
            conn.commit()
    except Exception as db_err:
        logger.error(
            f"Failed to upsert graph trace status: {db_err}",
            extra={
                "event": "trace_status_upsert_failed",
                "run_id": run_id,
                "langsmith_run_id": langsmith_run_id,
                "trace_status": status,
            },
        )


def export_graph_trace(run_id: str, langsmith_run_id: str | None) -> None:
    """
    Export full LangSmith trace to Supabase Storage for a completed graph run.

    This function is intentionally non-blocking for the request lifecycle:
    all exceptions are handled internally and logged.
    """
    if not langsmith_run_id:
        reason = "langsmith_run_id not provided"
        _upsert_trace_status(
            run_id=run_id,
            langsmith_run_id=None,
            status="skipped",
            error_message=reason,
        )
        logger.warning(
            "Skipping graph trace export: missing LangSmith run id",
            extra={"event": "trace_export_skipped", "run_id": run_id, "reason": reason},
        )
        return

    if not _is_tracing_enabled():
        reason = "LANGCHAIN_TRACING_V2 is disabled"
        _upsert_trace_status(
            run_id=run_id,
            langsmith_run_id=langsmith_run_id,
            status="skipped",
            error_message=reason,
        )
        logger.info(
            "Skipping graph trace export: tracing disabled",
            extra={
                "event": "trace_export_skipped",
                "run_id": run_id,
                "langsmith_run_id": langsmith_run_id,
                "reason": reason,
            },
        )
        return

    if not os.getenv("LANGSMITH_API_KEY"):
        reason = "LANGSMITH_API_KEY not configured"
        _upsert_trace_status(
            run_id=run_id,
            langsmith_run_id=langsmith_run_id,
            status="skipped",
            error_message=reason,
        )
        logger.warning(
            "Skipping graph trace export: LangSmith API key missing",
            extra={
                "event": "trace_export_skipped",
                "run_id": run_id,
                "langsmith_run_id": langsmith_run_id,
                "reason": reason,
            },
        )
        return

    ls_client = _get_langsmith_client()
    if ls_client is None:
        reason = "langsmith package not installed"
        _upsert_trace_status(
            run_id=run_id,
            langsmith_run_id=langsmith_run_id,
            status="skipped",
            error_message=reason,
        )
        logger.warning(
            "Skipping graph trace export: langsmith dependency unavailable",
            extra={
                "event": "trace_export_skipped",
                "run_id": run_id,
                "langsmith_run_id": langsmith_run_id,
                "reason": reason,
            },
        )
        return

    supabase = _get_supabase_client()
    if supabase is None:
        reason = "SUPABASE_PROJECT/SUPABASE_SECRET_KEY missing or supabase package unavailable"
        _upsert_trace_status(
            run_id=run_id,
            langsmith_run_id=langsmith_run_id,
            status="skipped",
            error_message=reason,
        )
        logger.warning(
            "Skipping graph trace export: Supabase configuration unavailable",
            extra={
                "event": "trace_export_skipped",
                "run_id": run_id,
                "langsmith_run_id": langsmith_run_id,
                "reason": reason,
            },
        )
        return

    bucket = os.getenv("SUPABASE_TRACES_BUCKET", "traces").strip() or "traces"
    object_path = f"{run_id}.json"
    storage_path = f"{bucket}/{object_path}"

    try:
        run = _read_langsmith_run_with_retry(ls_client, langsmith_run_id)
        trace_json = _serialize_run(run)
        size_bytes = len(trace_json)

        supabase.storage.from_(bucket).upload(
            path=object_path,
            file=trace_json,
            file_options={"content-type": "application/json", "upsert": "true"},
        )

        _upsert_trace_status(
            run_id=run_id,
            langsmith_run_id=langsmith_run_id,
            status="uploaded",
            storage_path=storage_path,
            size_bytes=size_bytes,
            error_message=None,
        )
        logger.info(
            "Graph trace exported",
            extra={
                "event": "trace_exported",
                "run_id": run_id,
                "langsmith_run_id": langsmith_run_id,
                "storage_path": storage_path,
                "size_bytes": size_bytes,
            },
        )
    except Exception as err:
        _upsert_trace_status(
            run_id=run_id,
            langsmith_run_id=langsmith_run_id,
            status="failed",
            storage_path=storage_path,
            error_message=str(err),
        )
        logger.error(
            f"Graph trace export failed: {err}",
            extra={
                "event": "trace_export_failed",
                "run_id": run_id,
                "langsmith_run_id": langsmith_run_id,
                "storage_path": storage_path,
            },
        )
