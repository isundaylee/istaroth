"""Tests for the first-seen game-version index."""

import pathlib

import orjson
import pytest

from istaroth.agd import first_seen


def _write_delta(
    data_dir: pathlib.Path, version: str, new: dict[str, list[int | str]]
) -> None:
    payload = {
        "version": version,
        "commit": f"commit-{version}",
        "new": {domain.value: [] for domain in first_seen.SourceDomain} | new,
    }
    (data_dir / f"{version}.json").write_bytes(orjson.dumps(payload))


@pytest.fixture
def data_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    _write_delta(
        tmp_path, "1.4", {"main_quest": [351], "talk": [100], "readable": ["Book1"]}
    )
    _write_delta(tmp_path, "2.0", {"talk": [200, 201]})
    # 10.0 ensures folding orders numerically, not lexicographically (10 > 2).
    _write_delta(tmp_path, "10.0", {"talk": [300]})
    return tmp_path


def test_resolve_min_max(data_dir: pathlib.Path) -> None:
    index = first_seen.FirstSeenIndex.load(data_dir)
    talk = first_seen.SourceDomain.TALK

    assert index.resolve([first_seen.SourceId(talk, 200)]) == ("2.0", "2.0")
    assert index.resolve(
        [
            first_seen.SourceId(talk, 300),
            first_seen.SourceId(talk, 100),
            first_seen.SourceId(talk, 201),
        ]
    ) == ("1.4", "10.0")
    assert index.resolve(
        [
            first_seen.SourceId(first_seen.SourceDomain.MAIN_QUEST, 351),
            first_seen.SourceId(first_seen.SourceDomain.READABLE, "Book1"),
        ]
    ) == ("1.4", "1.4")


def test_resolve_unknown_id_raises(data_dir: pathlib.Path) -> None:
    index = first_seen.FirstSeenIndex.load(data_dir)
    with pytest.raises(KeyError, match="not in the first-seen index"):
        index.resolve([first_seen.SourceId(first_seen.SourceDomain.TALK, 999)])
    with pytest.raises(ValueError, match="empty source ids"):
        index.resolve([])


def test_load_rejects_duplicate_id(data_dir: pathlib.Path) -> None:
    _write_delta(data_dir, "3.0", {"talk": [100]})
    with pytest.raises(ValueError, match="listed by both"):
        first_seen.FirstSeenIndex.load(data_dir)


@pytest.mark.parametrize(
    "stem,expected",
    [
        ("Book100_EN", "Book100"),
        ("Book100", "Book100"),
        ("Wanderer_Log_CHS", "Wanderer_Log"),
        ("Cs_Inazuma_JP", "Cs_Inazuma"),
    ],
)
def test_strip_language_suffix(stem: str, expected: str) -> None:
    assert first_seen.strip_language_suffix(stem) == expected
