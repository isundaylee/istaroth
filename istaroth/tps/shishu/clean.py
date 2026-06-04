"""Clean shishu chapter markdown for ingestion.

Each source file is already one chapter: line 1 is the ``# title`` heading and the
body carries website-specific markup (image embeds, ``<sup>`` footnotes, ``!!!``
callout delimiters, ``<commoncontent>`` wrappers, escaped-backtick fences wrapping
in-game quotes) that is normalized here.
"""

import re

_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BOLD_RE = re.compile(r"\*\*")

_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_SUP_RE = re.compile(r"<sup>(\d+)</sup>")
_EMPTY_SUP_RE = re.compile(r"<sup>\s*</sup>")
_COMMONCONTENT_RE = re.compile(r"</?commoncontent>")
_FOOTNOTE_DEF_RE = re.compile(r"^>\s*(\d+)\.?\s+(.*)$")
_CALLOUT_RE = re.compile(r"^!!!\s*$")
_BR_RE = re.compile(r"<br\s*/?>")
# The source wraps in-game quotes in escaped backticks (``\`\`\```) which render
# as literal backticks rather than a code fence; treat them as blockquote delimiters.
_FENCE_RE = re.compile(r"^(?:\\`){3}$|^`{3}.*$")


def _blockquote(text: str) -> str:
    """Prefix every line with a blockquote marker (``>`` alone for blank lines)."""
    return "\n".join(">" if not s.strip() else f"> {s}" for s in text.split("\n"))


def _extract_title(md_text: str) -> str:
    """Return the line-1 heading text, stripped of bold/HTML markup."""
    if not (m := _TITLE_RE.search(md_text)):
        raise ValueError("No level-1 heading found")
    return re.sub(
        r"\s+", " ", _HTML_TAG_RE.sub("", _BOLD_RE.sub("", m.group(1)))
    ).strip()


def clean_chapter(md_text: str) -> tuple[str, str]:
    """Return ``(title, cleaned_body)`` for one chapter markdown file."""
    title = _extract_title(md_text)

    text = _IMAGE_RE.sub("", md_text)
    text = _COMMONCONTENT_RE.sub("", text)
    text = _SUP_RE.sub(r"[^\1]", text)
    text = _EMPTY_SUP_RE.sub("", text)

    lines: list[str] = []
    in_quote = False
    for line in text.splitlines():
        if _FENCE_RE.match(line.strip()):
            in_quote = not in_quote
            continue
        if _CALLOUT_RE.match(line):
            continue
        line = _FOOTNOTE_DEF_RE.sub(r"[^\1]: \2", line)
        # A table row must stay on one physical line, so collapse in-cell <br>
        # to a space; elsewhere it becomes a real line break.
        line = _BR_RE.sub(" " if line.lstrip().startswith("|") else "\n", line)
        if in_quote:
            line = _blockquote(line)
        lines.append(line)

    return title, re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"
