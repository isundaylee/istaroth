"""Tests for AGD repository helpers."""

from istaroth.agd import agd_types, localization, repo


def test_text_map_tracker_uses_fallback_only_on_current_miss() -> None:
    """Fallback TextMap entries recover dropped hashes without overriding current text."""
    text_map = repo.TextMapTracker(
        {"100": "Current", "200": "Current wins"},
        localization.Language.ENG,
        {"200": "Fallback loses", "300": "Fallback"},
        pronoun_map={},
    )

    assert text_map.has(100)
    assert text_map.has(300)
    assert text_map.get_optional(100) == "Current"
    assert text_map.get_optional(200) == "Current wins"
    assert text_map.get_optional(300) == "Fallback"
    assert text_map.get_current_optional(300) is None
    assert text_map.get_optional_untracked(300) == "Fallback"
    assert text_map.get(400, "Default") == "Default"
    assert text_map.get_accessed_ids() == {100, 200, 300}


def test_data_repo_loads_fallback_refs_in_code_order(monkeypatch) -> None:
    """Earlier fallback refs take priority over later refs."""
    data_repo = repo.DataRepo(".", language=localization.Language.ENG)
    monkeypatch.setattr(repo, "_TEXT_MAP_FALLBACK_REFS", ("newer", "older"))

    def _fake_git_show_text_map(
        _data_repo: repo.DataRepo, fallback_ref: str, filename: str, *, required: bool
    ) -> agd_types.TextMap | None:
        if filename.startswith("TextMap_Medium"):
            return None
        return {
            "newer": {"100": "Newer", "200": "Newer only"},
            "older": {"100": "Older", "300": "Older only"},
        }[fallback_ref]

    monkeypatch.setattr(repo.DataRepo, "_git_show_text_map", _fake_git_show_text_map)

    assert data_repo._load_fallback_text_map("EN") == {
        "100": "Newer",
        "200": "Newer only",
        "300": "Older only",
    }
