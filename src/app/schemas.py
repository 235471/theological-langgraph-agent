"""
API Schemas — Request/Response validation and sanitization.

Uses Pydantic for strict validation (Python equivalent of Zod).
"""

import re
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class VerseResponse(BaseModel):
    number: int
    text: str


class AnalyzeRequest(BaseModel):
    """
    Request payload for theological analysis.
    Strict validation and sanitization on all fields.
    """

    book: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Book abbreviation (e.g., 'Sl' for Psalms)",
    )
    chapter: int = Field(
        ...,
        ge=1,
        le=200,
        description="Chapter number (1-indexed)",
    )
    verses: List[int] = Field(
        ...,
        min_length=1,
        max_length=200,
        description="List of verse numbers to analyze",
    )
    selected_modules: List[str] = Field(
        ...,
        min_length=1,
        description="Analysis modules to run",
    )

    @field_validator("book")
    @classmethod
    def sanitize_book(cls, v: str) -> str:
        """Strip whitespace and validate alphanumeric characters."""
        v = v.strip()
        if not re.match(r"^[a-zA-ZÀ-ÿ0-9]+$", v):
            raise ValueError(f"Book abbreviation must be alphanumeric. Got: '{v}'")
        return v

    @field_validator("selected_modules")
    @classmethod
    def validate_modules(cls, v: List[str]) -> List[str]:
        """Validate against whitelist and deduplicate."""
        valid_modules = {"panorama", "exegese", "teologia"}
        sanitized = []
        for module in v:
            module = module.strip().lower()
            if module not in valid_modules:
                raise ValueError(f"Invalid module: '{module}'. Valid: {valid_modules}")
            if module not in sanitized:
                sanitized.append(module)
        return sanitized

    @field_validator("verses")
    @classmethod
    def validate_verses(cls, v: List[int]) -> List[int]:
        """Validate verse numbers and deduplicate."""
        if not v:
            raise ValueError("At least one verse must be selected")
        for verse in v:
            if verse < 1:
                raise ValueError(f"Verse number must be >= 1. Got: {verse}")
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for verse in v:
            if verse not in seen:
                seen.add(verse)
                deduped.append(verse)
        return deduped


class AnalyzeResponse(BaseModel):
    """
    Response from theological analysis.
    Includes governance metadata for observability.
    """

    final_analysis: str
    from_cache: bool = False
    run_id: Optional[str] = None
    tokens_consumed: Optional[dict] = None
    model_versions: Optional[dict] = None
    risk_level: Optional[str] = None
    hitl_status: Optional[str] = None


class HITLReviewResponse(BaseModel):
    """Response for a single HITL review."""

    run_id: str
    book: str
    chapter: int
    verses: List[int]
    risk_level: str
    alerts: List[str]
    validation_content: Optional[str] = None
    panorama_content: Optional[str] = None
    lexical_content: Optional[str] = None
    historical_content: Optional[str] = None
    intertextual_content: Optional[str] = None
    selected_modules: List[str] = []
    edited_content: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    model_versions: Optional[dict] = None
    tokens_consumed: Optional[dict] = None
    reasoning_steps: Optional[list] = None


class HITLApproveRequest(BaseModel):
    """Request to approve or edit a HITL review."""

    edited_content: Optional[str] = None
