"""Tests for AGD de-obfuscation functionality."""

import json

import pytest

from istaroth.agd import deobfuscation, repo


def test_deobfuscate_quest_data(data_repo: repo.DataRepo) -> None:
    """Test de-obfuscation using quest 1000.json from AGD repo."""
    quest_path = "BinOutput/Quest/1000.json"
    quest_file = data_repo.agd_path / quest_path

    # Load raw JSON data
    with quest_file.open(encoding="utf-8") as f:
        raw_data = json.load(f)

    # De-obfuscate the data
    deobfuscated_data = deobfuscation.deobfuscate_quest_data(raw_data)

    # Assert fixed values
    assert deobfuscated_data["id"] == 1000
    assert deobfuscated_data["descTextMapHash"] == 911637991
    assert deobfuscated_data["titleTextMapHash"] == 492421553
    assert deobfuscated_data["chapterId"] == 1101
    assert len(deobfuscated_data["subQuests"]) > 0
    assert deobfuscated_data["subQuests"][0]["subId"] == 100000
    assert deobfuscated_data["subQuests"][0]["order"] == 3
    assert len(deobfuscated_data["talks"]) > 0
    assert deobfuscated_data["talks"][0]["id"] == 100001

    # Verify that load_quest_data returns the same structure
    loaded_data = data_repo.load_quest_data(quest_path)
    assert loaded_data["id"] == 1000
    assert loaded_data["descTextMapHash"] == 911637991
