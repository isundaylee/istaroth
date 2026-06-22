"""Tests for retrieval-quality eval fixtures."""

import pytest

from istaroth.rag.eval import retrieval


def test_dataset_loads_and_validates():
    """The fixtures load, pass structural validation, and are non-empty."""
    dataset = retrieval.load_retrieval_dataset()
    assert dataset.fixtures
    assert "breadth" in dataset.categories


@pytest.mark.parametrize(
    "fixture",
    retrieval.load_retrieval_dataset().fixtures,
    ids=lambda f: f"{f.category}-{f.subtype or ''}",
)
def test_every_passage_self_matches(fixture: retrieval.RetrievalFixture):
    """A passage is found in its own text, and matching ignores whitespace."""
    for passage in fixture.relevant_passages:
        assert passage.matches(passage.passage)
        rewrapped = "\n".join(passage.passage) + "  trailing"
        assert passage.matches(rewrapped), f"{passage.label!r} broke under re-wrapping"


@pytest.mark.parametrize(
    "fixture",
    retrieval.load_retrieval_dataset().fixtures,
    ids=lambda f: f"{f.category}-{f.subtype or ''}",
)
def test_full_ranking_covers_all_facets(fixture: retrieval.RetrievalFixture):
    """Feeding every passage's text as a separate source covers all facets."""
    texts = [p.passage for p in fixture.relevant_passages]
    assert fixture.coverage_at_k(texts, len(texts)) == set(fixture.expected_coverage)


@pytest.mark.parametrize(
    "fixture",
    retrieval.load_retrieval_dataset().fixtures,
    ids=lambda f: f"{f.category}-{f.subtype or ''}",
)
def test_coverage_curve_is_monotonic(fixture: retrieval.RetrievalFixture):
    """Coverage only grows as the cutoff k increases."""
    texts = [p.passage for p in fixture.relevant_passages]
    counts = [count for _, count in fixture.coverage_curve(texts)]
    assert counts == sorted(counts)


def test_facets_in_ignores_unrelated_text():
    """An irrelevant blob covers nothing."""
    fixture = retrieval.load_retrieval_dataset().fixtures[0]
    assert fixture.facets_in("这是一段完全无关的文本。") == set()


def test_known_redundancy_is_recorded_somewhere():
    """At least one fixture documents a near-duplicate source pair (motivates dedup/MMR)."""
    assert any(f.known_redundancy for f in retrieval.load_retrieval_dataset().fixtures)


@pytest.mark.parametrize(
    "span, texts, expected",
    [
        ("钟离", ["无关", "岩 王 帝\n君钟 离"], 2),
        ("钟离", ["温迪", "纳西妲"], None),
        ("温迪", ["温迪是风神"], 1),
    ],
)
def test_locate_span(span, texts, expected):
    """Span location ignores whitespace and returns the first containing rank."""
    assert retrieval.locate_span(span, texts) == expected


def _raw_fixture(**overrides):
    raw = {
        "query": "测试问题",
        "language": "CHS",
        "rationale": "r",
        "expected_coverage": ["a", "b"],
        "relevant_passages": [
            {"passage": "甲文本", "label": "甲标签", "official": True, "covers": ["a"]},
            {"passage": "乙文本", "label": "乙标签", "official": True, "covers": ["b"]},
        ],
    }
    raw.update(overrides)
    return raw


def test_facet_description_falls_back_to_anchor_labels():
    """Without an explicit description, a facet's anchor labels are used."""
    fixture = retrieval._parse_fixture("breadth", _raw_fixture())
    assert fixture.facet_description("a") == "甲标签"


def test_facet_description_prefers_explicit():
    """An explicit facet_descriptions entry overrides the label fallback."""
    fixture = retrieval._parse_fixture(
        "breadth", _raw_fixture(facet_descriptions={"a": "明确描述"})
    )
    assert fixture.facet_description("a") == "明确描述"


def test_facet_descriptions_rejects_unknown_facet():
    """facet_descriptions naming a non-expected facet is a validation error."""
    with pytest.raises(ValueError, match="unknown facet"):
        retrieval._parse_fixture(
            "breadth", _raw_fixture(facet_descriptions={"zzz": "x"})
        )
