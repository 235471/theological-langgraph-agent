import json
from pathlib import Path
from typing import List, Dict, Optional

# Load NAA.json at module startup
NAA_PATH = Path(__file__).parent.parent.parent.parent / "resources" / "NAA.json"

_bible_data: List[Dict] = []


def _load_bible_data():
    global _bible_data
    if not _bible_data:
        with open(NAA_PATH, "r", encoding="utf-8") as f:
            _bible_data = json.load(f)
    return _bible_data


def get_book_by_abbrev(abbrev: str) -> Optional[Dict]:
    """Find a book by its abbreviation."""
    data = _load_bible_data()
    for book in data:
        if book["abbrev"].lower() == abbrev.lower():
            return book
    return None


def get_verses(abbrev: str, chapter: int) -> List[Dict[str, any]]:
    """
    Get all verses for a specific book and chapter.

    Args:
        abbrev: Book abbreviation (e.g., "Gn", "Sl")
        chapter: Chapter number (1-indexed)

    Returns:
        List of dicts with 'number' and 'text' keys
    """
    book = get_book_by_abbrev(abbrev)
    if not book:
        return []

    chapters = book.get("chapters", [])
    # Chapter is 1-indexed, array is 0-indexed
    chapter_index = chapter - 1

    if chapter_index < 0 or chapter_index >= len(chapters):
        return []

    verses_texts = chapters[chapter_index]

    # Convert to list of dicts with number and text
    verses = [
        {"number": i + 1, "text": verse_text}
        for i, verse_text in enumerate(verses_texts)
    ]

    return verses


def get_specific_verses(
    abbrev: str, chapter: int, verse_numbers: List[int]
) -> List[str]:
    """
    Get specific verse texts by their numbers.

    Args:
        abbrev: Book abbreviation
        chapter: Chapter number (1-indexed)
        verse_numbers: List of verse numbers to retrieve

    Returns:
        List of verse text strings
    """
    all_verses = get_verses(abbrev, chapter)
    verse_dict = {v["number"]: v["text"] for v in all_verses}

    return [verse_dict.get(num, "") for num in verse_numbers if num in verse_dict]


def get_book_chapter_count(abbrev: str) -> int:
    """Get the total number of chapters in a book."""
    book = get_book_by_abbrev(abbrev)
    if not book:
        return 0
    return len(book.get("chapters", []))
