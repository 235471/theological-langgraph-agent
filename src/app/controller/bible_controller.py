from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas import VerseResponse
from app.service.bible_service import get_verses, get_book_by_abbrev

router = APIRouter(prefix="/bible", tags=["Bible"])


@router.get(
    "/{abbrev}/{chapter}/verses",
    response_model=List[VerseResponse],
    summary="Get verses for a chapter",
    description="Retrieves all verses for a specific book abbreviation and chapter number.",
)
async def get_chapter_verses(abbrev: str, chapter: int):
    """
    Retrieve all verses for a specific book and chapter.

    - **abbrev**: Book abbreviation (e.g., "Gn" for Genesis, "Sl" for Psalms)
    - **chapter**: Chapter number (1-indexed)
    """
    # Validate book exists
    book = get_book_by_abbrev(abbrev)
    if not book:
        raise HTTPException(
            status_code=404, detail=f"Book with abbreviation '{abbrev}' not found"
        )

    # Validate chapter number
    total_chapters = len(book.get("chapters", []))
    if chapter < 1 or chapter > total_chapters:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter {chapter} not found. Book '{abbrev}' has {total_chapters} chapters.",
        )

    verses = get_verses(abbrev, chapter)

    if not verses:
        raise HTTPException(
            status_code=404, detail=f"No verses found for {abbrev} chapter {chapter}"
        )

    return verses
