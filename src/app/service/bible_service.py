import json
from pathlib import Path
from typing import List, Dict, Optional

# Path to the Bible JSON
NAA_PATH = Path(__file__).parent.parent.parent.parent / "resources" / "NAA.json"

# Global variable to cache the data
_bible_data_cache: Optional[List[Dict]] = None


def get_bible_data() -> List[Dict]:
    """Lazy load Bible data only when needed and cache it."""
    global _bible_data_cache
    if _bible_data_cache is None:
        try:
            with open(NAA_PATH, "r", encoding="utf-8") as f:
                _bible_data_cache = json.load(f)
        except Exception as e:
            print(f"❌ Error loading Bible data: {e}")
            return []
    return _bible_data_cache


def get_book_by_abbrev(abbrev: str) -> Optional[Dict]:
    """Find a book by its abbreviation."""
    data = get_bible_data()
    for book in data:
        if book["abbrev"].lower() == abbrev.lower():
            return book
    return None


def get_verses(abbrev: str, chapter: int) -> List[Dict[str, any]]:
    """Get all verses for a specific book and chapter."""
    book = get_book_by_abbrev(abbrev)
    if not book:
        return []

    chapters = book.get("chapters", [])
    chapter_index = chapter - 1

    if chapter_index < 0 or chapter_index >= len(chapters):
        return []

    verses_texts = chapters[chapter_index]
    return [
        {"number": i + 1, "text": verse_text}
        for i, verse_text in enumerate(verses_texts)
    ]


def get_specific_verses(
    abbrev: str, chapter: int, verse_numbers: List[int]
) -> List[str]:
    """Get specific verse texts by their numbers."""
    all_verses = get_verses(abbrev, chapter)
    verse_dict = {v["number"]: v["text"] for v in all_verses}
    return [verse_dict.get(num, "") for num in verse_numbers if num in verse_dict]


def get_book_chapter_count(abbrev: str) -> int:
    """Get the total number of chapters in a book."""
    book = get_book_by_abbrev(abbrev)
    return len(book.get("chapters", [])) if book else 0
