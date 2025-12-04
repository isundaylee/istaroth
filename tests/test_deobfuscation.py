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


def test_deobfuscate_talk_data(data_repo: repo.DataRepo) -> None:
    """Test de-obfuscation using talk 4002015.json from AGD repo."""
    talk_path = "BinOutput/Talk/Activity/4002015.json"
    talk_file = data_repo.agd_path / talk_path

    # Load raw JSON data
    with talk_file.open(encoding="utf-8") as f:
        raw_data = json.load(f)

    # De-obfuscate the data
    deobfuscated_data = deobfuscation.deobfuscate_talk_data(raw_data)

    # Assert fixed values
    assert deobfuscated_data["talkId"] == 4002015
    assert len(deobfuscated_data["dialogList"]) > 0
    assert deobfuscated_data["dialogList"][0]["id"] == 400201501
    assert deobfuscated_data["dialogList"][0]["talkRole"]["type"] == "TALK_ROLE_NPC"
    assert deobfuscated_data["dialogList"][0]["talkRole"]["_id"] == "12172"
    assert deobfuscated_data["dialogList"][0]["talkContentTextMapHash"] == 3440950762

    # Verify that load_talk_data returns the same structure
    loaded_data = data_repo.load_talk_data(talk_path)
    assert loaded_data["talkId"] == 4002015
    assert loaded_data["dialogList"][0]["id"] == 400201501
