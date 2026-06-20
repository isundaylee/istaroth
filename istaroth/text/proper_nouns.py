"""Proper-noun dictionary helpers."""

import pathlib
from collections.abc import Iterable

PROPER_NOUNS_RELATIVE_PATH = pathlib.Path("misc/proper_nouns.txt")
PROPER_NOUNS_NEGATIVE_RELATIVE_PATH = pathlib.Path("misc/proper_nouns_negative.txt")


def parse_terms(content: str | None) -> list[str]:
    """Parse newline-delimited terms, allowing blank lines and comments."""
    if content is None:
        return []
    return [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _is_auto_excluded(term: str) -> bool:
    return len(term) == 1 or "█" in term


def filter_terms(terms: Iterable[str], negative_terms: Iterable[str]) -> list[str]:
    """Return terms after automatic and maintained exclusions."""
    excluded = set(negative_terms)
    return [
        term for term in terms if term not in excluded and not _is_auto_excluded(term)
    ]


def filter_terms_from_content(
    content: str | None, negative_content: str | None
) -> list[str]:
    """Parse and filter a proper-noun file plus its negative list."""
    return filter_terms(parse_terms(content), parse_terms(negative_content))


def load_negative_terms(text_path: pathlib.Path) -> list[str]:
    """Load the maintained negative list from a language text directory."""
    negative_path = text_path / PROPER_NOUNS_NEGATIVE_RELATIVE_PATH
    return parse_terms(negative_path.read_text() if negative_path.exists() else None)


def load_terms(text_path: pathlib.Path) -> list[str]:
    """Load filtered proper nouns from a language text directory."""
    proper_nouns_path = text_path / PROPER_NOUNS_RELATIVE_PATH
    return filter_terms(
        parse_terms(
            proper_nouns_path.read_text() if proper_nouns_path.exists() else None
        ),
        load_negative_terms(text_path),
    )
