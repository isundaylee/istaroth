"""Discover and download shishu chapter markdown from genshinlore.github.io."""

import re

import httpx

INDEX_URL = "https://genshinlore.github.io/md.html"
FILE_BASE_URL = "https://genshinlore.github.io/md"

# Non-lore pages (about the website, author commentary) to skip.
EXCLUDED_STEMS = frozenset({"aboutsite", "somewords"})

_LINK_RE = re.compile(r'href="/md/(\w+)\.md"')


def list_chapter_stems(*, client: httpx.Client) -> list[str]:
    """Return chapter file stems from the index page, in document order, excluding meta pages."""
    response = client.get(INDEX_URL)
    response.raise_for_status()
    stems: list[str] = []
    for stem in _LINK_RE.findall(response.text):
        if stem not in EXCLUDED_STEMS and stem not in stems:
            stems.append(stem)
    if not stems:
        raise ValueError(f"No chapter links found at {INDEX_URL}")
    return stems


def download(stem: str, *, client: httpx.Client) -> str:
    """Download the markdown for a single chapter stem."""
    response = client.get(f"{FILE_BASE_URL}/{stem}.md")
    response.raise_for_status()
    return response.text
