"""
HITL Service

Handles Human-in-the-Loop review logic:
- Persist pending reviews to hitl_reviews table
- List/get pending reviews
- Approve or edit-and-approve reviews (resumes synthesis)
"""

import json
from typing import Optional
from dataclasses import dataclass

from app.database.connection import get_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HITLReview:
    """Represents a pending HITL review."""

    run_id: str
    book: str
    chapter: int
    verses: list[int]
    risk_level: str
    alerts: list[str]
    validation_content: str
    panorama_content: Optional[str]
    lexical_content: Optional[str]
    historical_content: Optional[str]
    intertextual_content: Optional[str]
    selected_modules: list[str]
    status: str
    created_at: str
    model_versions: Optional[dict] = None
    prompt_versions: Optional[dict] = None
    tokens_consumed: Optional[dict] = None
    reasoning_steps: Optional[list] = None
    edited_content: Optional[str] = None
    reviewed_at: Optional[str] = None


def save_pending_review(
    run_id: str,
    book: str,
    chapter: int,
    verses: list[int],
    risk_level: str,
    alerts: list[str],
    validation_content: str,
    selected_modules: list[str],
    panorama_content: Optional[str] = None,
    lexical_content: Optional[str] = None,
    historical_content: Optional[str] = None,
    intertextual_content: Optional[str] = None,
    model_versions: Optional[dict] = None,
    prompt_versions: Optional[dict] = None,
    tokens_consumed: Optional[dict] = None,
    reasoning_steps: Optional[list] = None,
) -> None:
    """Save a high-risk analysis as pending review."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hitl_reviews (
                        run_id, book, chapter, verses, risk_level, alerts,
                        validation_content, panorama_content, lexical_content,
                        historical_content, intertextual_content, selected_modules,
                        model_versions, prompt_versions, tokens_consumed, reasoning_steps,
                        status
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        'pending'
                    )
                    ON CONFLICT (run_id) DO NOTHING
                    """,
                    (
                        run_id,
                        book,
                        chapter,
                        verses,
                        risk_level,
                        alerts,
                        validation_content,
                        panorama_content,
                        lexical_content,
                        historical_content,
                        intertextual_content,
                        selected_modules,
                        json.dumps(model_versions) if model_versions else None,
                        json.dumps(prompt_versions) if prompt_versions else None,
                        json.dumps(tokens_consumed) if tokens_consumed else None,
                        json.dumps(reasoning_steps) if reasoning_steps else None,
                    ),
                )
            conn.commit()

        logger.info(
            "HITL review saved as pending",
            extra={"event": "hitl_pending", "run_id": run_id, "risk_level": risk_level},
        )

    except Exception as e:
        logger.error(f"Failed to save HITL review: {e}", extra={"run_id": run_id})
        raise


def get_pending_reviews() -> list[dict]:
    """Get all pending HITL reviews."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT run_id, book, chapter, verses, risk_level, alerts,
                           status, created_at
                    FROM hitl_reviews
                    WHERE status = 'pending'
                    ORDER BY created_at DESC
                    """
                )
                rows = cur.fetchall()

        return [
            {
                "run_id": row[0],
                "book": row[1],
                "chapter": row[2],
                "verses": row[3],
                "risk_level": row[4],
                "alerts": row[5],
                "status": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
            }
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Failed to fetch pending reviews: {e}")
        return []


def get_review(run_id: str) -> Optional[dict]:
    """Get full details of a HITL review."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT run_id, book, chapter, verses, risk_level, alerts,
                           validation_content, panorama_content, lexical_content,
                           historical_content, intertextual_content, selected_modules,
                           edited_content, status, created_at, reviewed_at,
                           model_versions, prompt_versions, tokens_consumed, reasoning_steps
                    FROM hitl_reviews
                    WHERE run_id = %s
                    """,
                    (run_id,),
                )
                row = cur.fetchone()

        if not row:
            return None

        return {
            "run_id": row[0],
            "book": row[1],
            "chapter": row[2],
            "verses": row[3],
            "risk_level": row[4],
            "alerts": row[5],
            "validation_content": row[6],
            "panorama_content": row[7],
            "lexical_content": row[8],
            "historical_content": row[9],
            "intertextual_content": row[10],
            "selected_modules": row[11],
            "edited_content": row[12],
            "status": row[13],
            "created_at": row[14].isoformat() if row[14] else None,
            "reviewed_at": row[15].isoformat() if row[15] else None,
            "model_versions": json.loads(row[16]) if row[16] else None,
            "prompt_versions": json.loads(row[17]) if row[17] else None,
            "tokens_consumed": json.loads(row[18]) if row[18] else None,
            "reasoning_steps": json.loads(row[19]) if row[19] else None,
        }

    except Exception as e:
        logger.error(f"Failed to fetch review {run_id}: {e}")
        return None


def approve_review(run_id: str, edited_content: Optional[str] = None) -> bool:
    """
    Approve a HITL review, optionally with edited validation content.

    Args:
        run_id: The run ID to approve
        edited_content: If provided, replaces the validation_content for synthesis

    Returns:
        True if the review was approved, False otherwise
    """
    try:
        status = "edited" if edited_content else "approved"

        with get_connection() as conn:
            with conn.cursor() as cur:
                if edited_content:
                    cur.execute(
                        """
                        UPDATE hitl_reviews
                        SET status = %s,
                            edited_content = %s,
                            reviewed_at = NOW()
                        WHERE run_id = %s AND status = 'pending'
                        RETURNING run_id
                        """,
                        (status, edited_content, run_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE hitl_reviews
                        SET status = %s,
                            reviewed_at = NOW()
                        WHERE run_id = %s AND status = 'pending'
                        RETURNING run_id
                        """,
                        (status, run_id),
                    )
                result = cur.fetchone()
            conn.commit()

        if result:
            logger.info(
                f"HITL review {status}",
                extra={"event": f"hitl_{status}", "run_id": run_id},
            )
            return True

        return False

    except Exception as e:
        logger.error(f"Failed to approve review {run_id}: {e}")
        return False


def get_validation_content_for_synthesis(run_id: str) -> Optional[str]:
    """
    Get the validation content to use for synthesis.
    Uses edited_content if available, otherwise uses original validation_content.
    """
    review = get_review(run_id)
    if not review:
        return None

    return review.get("edited_content") or review.get("validation_content")
