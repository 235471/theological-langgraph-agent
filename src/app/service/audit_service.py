"""
Audit Service

Persists every analysis run (success or failure) to the analysis_runs table
for governance, debugging, and observability.
"""

import json
from typing import Any, Optional

from app.database.connection import get_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)


def save_run(
    run_id: str,
    book: str,
    chapter: int,
    verses: list[int],
    selected_modules: list[str],
    success: bool,
    final_analysis: str = "",
    error: Optional[str] = None,
    model_versions: Optional[dict] = None,
    prompt_versions: Optional[dict] = None,
    tokens_consumed: Optional[dict] = None,
    reasoning_steps: Optional[list] = None,
    risk_level: Optional[str] = None,
    hitl_status: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """
    Persist an analysis run to the audit table.

    Always called — on success AND failure — for full auditability.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analysis_runs (
                        run_id, book, chapter, verses, selected_modules,
                        model_versions, prompt_versions, tokens_consumed, reasoning_steps,
                        risk_level, hitl_status, final_analysis,
                        success, error, duration_ms
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    )
                    ON CONFLICT (run_id) DO UPDATE SET
                        final_analysis = EXCLUDED.final_analysis,
                        success = EXCLUDED.success,
                        error = EXCLUDED.error,
                        hitl_status = EXCLUDED.hitl_status,
                        duration_ms = EXCLUDED.duration_ms
                    """,
                    (
                        run_id,
                        book,
                        chapter,
                        verses,
                        selected_modules,
                        json.dumps(model_versions) if model_versions else None,
                        json.dumps(prompt_versions) if prompt_versions else None,
                        json.dumps(tokens_consumed) if tokens_consumed else None,
                        json.dumps(reasoning_steps) if reasoning_steps else None,
                        risk_level,
                        hitl_status,
                        final_analysis,
                        success,
                        error,
                        duration_ms,
                    ),
                )
            conn.commit()

        logger.info(
            "Audit run saved",
            extra={"event": "audit_saved", "run_id": run_id, "success": success},
        )

    except Exception as e:
        # Audit failures must never break the main flow
        logger.error(
            f"Audit save failed: {e}",
            extra={"event": "audit_error", "run_id": run_id},
        )
