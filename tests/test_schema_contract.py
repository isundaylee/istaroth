"""Contract tests for the JSON schemas shared between the Rust writer and Python readers.

The fixtures under ``tests/fixtures/rust_agd_regen_contract/`` are shared with the Rust half
(``rust/istaroth-agd-regen/tests/contract.rs``): that side pins the writer's
serialization byte-exactly, this side pins the strict readers' round-trip. The
corpus tests additionally exercise the real committed ``text/`` submodule — the
actual interface artifact — and are skipped when it isn't checked out.
"""

import json
import pathlib

import attrs
import pytest

from istaroth import json_utils
from istaroth.agd import processed_types
from istaroth.services.backend import models
from istaroth.text import types

_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "rust_agd_regen_contract"
_TEXT_DIR = pathlib.Path(__file__).parent.parent / "text"

_requires_corpus = pytest.mark.skipif(
    not (_TEXT_DIR / "chs" / "manifest").is_dir(),
    reason="text/ corpus submodule not checked out",
)


def test_manifest_fixture_round_trip() -> None:
    raw = (_FIXTURE_DIR / "manifest.json").read_bytes()
    assert (
        json_utils.dumps_indented(
            [types.TextMetadata.from_dict(entry).to_dict() for entry in json.loads(raw)]
        )
        == raw
    )


def test_hierarchy_fixture_round_trip() -> None:
    raw = (_FIXTURE_DIR / "hierarchy.json").read_bytes()
    assert (
        json_utils.dumps_indented(
            {
                category: processed_types.Hierarchy.from_dict(hierarchy).to_dict()
                for category, hierarchy in json.loads(raw).items()
            }
        )
        == raw
    )


def test_from_dict_rejects_unexpected_keys() -> None:
    entry = json.loads((_FIXTURE_DIR / "manifest.json").read_bytes())[0]
    with pytest.raises(ValueError, match="Manifest entry keys"):
        types.TextMetadata.from_dict(entry | {"extra": 1})
    node = json.loads((_FIXTURE_DIR / "hierarchy.json").read_bytes())["agd_quest"][
        "nodes"
    ][0]
    with pytest.raises(ValueError, match="Hierarchy node keys"):
        processed_types.HierarchyNode.from_dict(node | {"extra": 1})
    with pytest.raises(ValueError, match="Hierarchy keys"):
        processed_types.Hierarchy.from_dict({"nodes": [], "extra": 1})


@_requires_corpus
@pytest.mark.parametrize("language", ["chs", "eng"])
def test_corpus_manifest_round_trip(language: str) -> None:
    paths = sorted((_TEXT_DIR / language / "manifest").glob("*.json"))
    assert paths
    for path in paths:
        for entry in json.loads(path.read_bytes()):
            assert types.TextMetadata.from_dict(entry).to_dict() == entry


@_requires_corpus
@pytest.mark.parametrize("language", ["chs", "eng"])
def test_corpus_hierarchy_round_trip(language: str) -> None:
    data = json.loads(
        (_TEXT_DIR / language / "metadata" / "agd" / "hierarchy.json").read_bytes()
    )
    assert set(data) == {"agd_quest", "agd_hangout"}
    for hierarchy in data.values():
        assert processed_types.Hierarchy.from_dict(hierarchy).to_dict() == hierarchy


@_requires_corpus
@pytest.mark.parametrize("language", ["chs", "eng"])
def test_corpus_covers_all_agd_categories(language: str) -> None:
    # Strict from_dict already proves Rust-emitted categories are a subset of
    # the enum; equality here additionally catches stale enum members.
    entries = json.loads((_TEXT_DIR / language / "manifest" / "agd.json").read_bytes())
    assert {entry["category"] for entry in entries} == {
        category.value for category in types.TextCategory if category.is_agd
    }


def test_api_models_field_parity() -> None:
    # The backend API models are hand-converted from these types
    # (istaroth/services/backend/utils.py, istaroth/rag/text_set.py); pin the
    # field sets so an additive change can't silently not be forwarded.
    assert {field.name for field in attrs.fields(types.TextMetadata)} == set(
        models.LibraryFileInfo.model_fields
    )
    assert {field.name for field in attrs.fields(processed_types.HierarchyNode)} | {
        "max_version"
    } == set(models.HierarchyNode.model_fields)
