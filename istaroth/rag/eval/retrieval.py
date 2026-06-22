"""Retrieval-quality eval fixtures.

A general harness for grading retrieval against passage-anchored ground truth.
For a query, each relevant source is anchored by a verbatim passage (a
distinctive substring of its text) tagged with the answer facet(s) it covers;
each fixture lists the full set of facets a complete answer should include. The
metric: run retrieval, match the anchors against retrieved source text, and count
how many facets are covered as the cutoff k grows.

Fixtures are grouped into CATEGORIES, one JSON file per category under
``retrieval_fixtures/`` (e.g. ``breadth.json``). The category determines what
retrieval property the fixtures probe; the machinery here is identical across
categories, so adding a new category is just adding a new JSON file.

Why anchor on passages (not file_id/chunk_index/score): the fixtures survive
re-chunking, re-embedding, path renames, and reranker changes — only the corpus
text matters. A facet is covered if ANY of its passages matches, so retrieval is
not penalized for surfacing a different-but-valid source than the first recorded.

Deriving ground truth
---------------------
Ground-truth passages are found by searching the ``text/`` corpus DIRECTLY (e.g.
``rg`` over ``text/chs``), NOT by reading off what the retrieval stack returns.
Seeding from retrieval output is circular: you only "discover" facets retrieval
already surfaces, so you undercount its misses. A direct corpus sweep instead
anchors each facet in authoritative sources retrieval may rank nowhere — turning a
coverage gap into evidence of a real retrieval miss. Give each facet several
anchors from distinct sources, prefer in-game canon (mark non-official sources
with ``official=False``), and anchor each on a short distinctive verbatim slice.
See the ``retrieval-fixtures`` skill for the full recipe.
"""

import functools
import json
import pathlib

import attrs

_FIXTURE_DIR = pathlib.Path(__file__).parent / "retrieval_fixtures"


def _normalize(text: str) -> str:
    """Drop all whitespace so passage matching is robust to chunk re-wrapping."""
    return "".join(text.split())


def locate_span(span: str, ranked_texts: list[str]) -> int | None:
    """1-based rank of the first ranked text containing `span` (whitespace-ignored)."""
    needle = _normalize(span)
    for rank, text in enumerate(ranked_texts, start=1):
        if needle in _normalize(text):
            return rank
    return None


@attrs.frozen
class RelevantPassage:
    """A relevant source anchored by a verbatim, distinctive substring."""

    passage: str
    label: str
    official: bool
    covers: tuple[str, ...]

    def matches(self, text: str) -> bool:
        """Whether this passage appears in `text` (ignoring whitespace)."""
        return _normalize(self.passage) in _normalize(text)


@attrs.frozen
class RetrievalFixture:
    """A query with passage-anchored ground truth for grading retrieval."""

    category: str
    query: str
    language: str
    subtype: str | None
    rationale: str
    expected_coverage: tuple[str, ...]
    relevant_passages: tuple[RelevantPassage, ...]
    facet_descriptions: dict[str, str]
    known_redundancy: str
    notes: str

    def facets_in(self, text: str) -> set[str]:
        """Expected facets whose passage appears in a single source's text."""
        expected = set(self.expected_coverage)
        return {
            facet
            for passage in self.relevant_passages
            if passage.matches(text)
            for facet in passage.covers
            if facet in expected
        }

    def coverage_at_k(self, ranked_texts: list[str], k: int) -> set[str]:
        """Expected facets covered by the top-k retrieved source texts."""
        covered: set[str] = set()
        for text in ranked_texts[:k]:
            covered |= self.facets_in(text)
        return covered

    def coverage_curve(self, ranked_texts: list[str]) -> list[tuple[int, int]]:
        """(k, facets-covered) for every cutoff over a ranked retrieval result."""
        return [
            (k, len(self.coverage_at_k(ranked_texts, k)))
            for k in range(1, len(ranked_texts) + 1)
        ]

    def first_covered_rank(self, ranked_texts: list[str]) -> dict[str, int | None]:
        """Rank (1-based) at which each expected facet is first covered, or None."""
        result: dict[str, int | None] = {f: None for f in self.expected_coverage}
        for rank, text in enumerate(ranked_texts, start=1):
            for facet in self.facets_in(text):
                if result[facet] is None:
                    result[facet] = rank
        return result


def _parse_fixture(category: str, raw: dict) -> RetrievalFixture:
    expected = tuple(raw["expected_coverage"])
    expected_set = set(expected)
    assert len(expected) == len(expected_set), f"Duplicate facet in {raw['query']!r}"

    passages = tuple(
        RelevantPassage(
            passage=p["passage"],
            label=p["label"],
            official=p["official"],
            covers=tuple(p["covers"]),
        )
        for p in raw["relevant_passages"]
    )
    for passage in passages:
        assert (
            passage.covers
        ), f"{raw['query']!r} passage {passage.label!r} covers nothing"
        if unknown := set(passage.covers) - expected_set:
            raise ValueError(
                f"{raw['query']!r} passage {passage.label!r} covers unknown facet(s): {unknown}"
            )

    covered = {facet for p in passages for facet in p.covers}
    if uncovered := expected_set - covered:
        raise ValueError(
            f"{raw['query']!r} expects facet(s) no passage covers: {uncovered}"
        )

    facet_descriptions = dict(raw.get("facet_descriptions", {}))
    if unknown := set(facet_descriptions) - expected_set:
        raise ValueError(
            f"{raw['query']!r} facet_descriptions name unknown facet(s): {unknown}"
        )

    return RetrievalFixture(
        category=category,
        query=raw["query"],
        language=raw["language"],
        subtype=raw.get("subtype"),
        rationale=raw["rationale"],
        expected_coverage=expected,
        relevant_passages=passages,
        facet_descriptions=facet_descriptions,
        known_redundancy=raw.get("known_redundancy", ""),
        notes=raw.get("notes", ""),
    )


@attrs.frozen
class RetrievalDataset:
    """All retrieval-eval fixtures across every category."""

    fixtures: tuple[RetrievalFixture, ...]

    @property
    def categories(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(f.category for f in self.fixtures))

    def by_category(self, category: str) -> tuple[RetrievalFixture, ...]:
        return tuple(f for f in self.fixtures if f.category == category)


def persist_anchors(anchors: list[tuple[str, str, dict]]) -> int:
    """Append judge-discovered anchors back into their category JSON files.

    `anchors` is a list of (category, query, passage-dict). New passages are
    appended to the matching fixture's ``relevant_passages``, skipping any whose
    ``passage`` text already exists there. Returns the number actually written.
    """
    written = 0
    by_category: dict[str, list[tuple[str, dict]]] = {}
    for category, query, passage in anchors:
        by_category.setdefault(category, []).append((query, passage))
    for category, items in by_category.items():
        path = _FIXTURE_DIR / f"{category}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        fixtures_by_query = {f["query"]: f for f in data["fixtures"]}
        # Sort appended anchors so output is independent of (concurrent) discovery
        # order; each anchor dict is already built with a fixed key order.
        for query, passage in sorted(
            items, key=lambda qp: (qp[0], qp[1]["covers"], qp[1]["passage"])
        ):
            fixture = fixtures_by_query[query]
            existing = {p["passage"] for p in fixture["relevant_passages"]}
            if passage["passage"] in existing:
                continue
            fixture["relevant_passages"].append(passage)
            written += 1
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    load_retrieval_dataset.cache_clear()
    return written


@functools.cache
def load_retrieval_dataset() -> RetrievalDataset:
    """Load and validate every category JSON under retrieval_fixtures/."""
    fixtures: list[RetrievalFixture] = []
    for path in sorted(_FIXTURE_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        category = data["category"]
        assert (
            category == path.stem
        ), f"{path.name}: category {category!r} must match filename"
        fixtures.extend(_parse_fixture(category, raw) for raw in data["fixtures"])
    assert fixtures, f"No fixtures found under {_FIXTURE_DIR}"
    return RetrievalDataset(fixtures=tuple(fixtures))
