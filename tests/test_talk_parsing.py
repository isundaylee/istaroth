"""Tests for AGD talk collision parsing."""

import collections
import pathlib
from unittest import mock

from istaroth.agd import localization, repo, talk_parsing


def test_talk_group_duplicate_resolution_prefers_canonical_id_path() -> None:
    parser = talk_parsing.TalkParser.__new__(talk_parsing.TalkParser)
    parser.talk_group_id_to_path = {}
    parser._talk_group_candidates = collections.defaultdict(list)

    parser._handle_talk_group_file(
        pathlib.Path("BinOutput/Talk/NpcGroup/cc9d0cc9.json"),
        "NpcGroup",
        {"talks": [{}], "npcId": 1292},
    )
    parser._handle_talk_group_file(
        pathlib.Path("BinOutput/Talk/NpcGroup/1292.json"),
        "NpcGroup",
        {"talks": [{}], "npcId": 1292},
    )
    parser._resolve_talk_group_candidates()

    assert (
        parser.talk_group_id_to_path[("NpcGroup", "1292")]
        == "BinOutput/Talk/NpcGroup/1292.json"
    )


def test_talk_group_gadget_uses_composite_config_group_key() -> None:
    """GadgetGroup files sharing a configId survive as distinct composite keys.

    A configId alone is not unique across GadgetGroup files (issue #186): the
    three ``1003`` variants are genuinely different talks (Opéra notices, Tubby,
    activity), each carrying a distinct ``groupId`` that disambiguates them.
    """
    parser = talk_parsing.TalkParser.__new__(talk_parsing.TalkParser)
    parser.talk_group_id_to_path = {}
    parser._talk_group_candidates = collections.defaultdict(list)

    for filename, group_id in [
        ("BinOutput/Talk/GadgetGroup/1003_201096001.json", 201096001),
        ("BinOutput/Talk/GadgetGroup/1003_220200001.json", 220200001),
        ("BinOutput/Talk/GadgetGroup/1003_999999900.json", 999999900),
    ]:
        parser._handle_talk_group_file(
            pathlib.Path(filename),
            "GadgetGroup",
            {"talks": [{}], "configId": 1003, "groupId": group_id},
        )
    parser._resolve_talk_group_candidates()

    # All three variants survive under their own (configId, groupId) composite.
    assert parser.talk_group_id_to_path == {
        ("GadgetGroup", "1003_201096001"): (
            "BinOutput/Talk/GadgetGroup/1003_201096001.json"
        ),
        ("GadgetGroup", "1003_220200001"): (
            "BinOutput/Talk/GadgetGroup/1003_220200001.json"
        ),
        ("GadgetGroup", "1003_999999900"): (
            "BinOutput/Talk/GadgetGroup/1003_999999900.json"
        ),
    }


def test_talk_group_gadget_prefers_canonical_named_composite() -> None:
    """A hash-named GadgetGroup file resolves via its in-data composite key and
    loses to a canonically-named file claiming the same composite (defensive:
    two distinct files with the same ``(configId, groupId)`` would be a data
    error, but the canonical-named copy wins if it ever happens)."""
    parser = talk_parsing.TalkParser.__new__(talk_parsing.TalkParser)
    parser.talk_group_id_to_path = {}
    parser._talk_group_candidates = collections.defaultdict(list)

    parser._handle_talk_group_file(
        pathlib.Path("BinOutput/Talk/GadgetGroup/4242_99.json"),
        "GadgetGroup",
        {"talks": [{}], "configId": 4242, "groupId": 99},
    )
    parser._handle_talk_group_file(
        pathlib.Path("BinOutput/Talk/GadgetGroup/26e54092.json"),
        "GadgetGroup",
        {"talks": [{}], "configId": 4242, "groupId": 99},
    )
    parser._resolve_talk_group_candidates()

    assert parser.talk_group_id_to_path == {
        ("GadgetGroup", "4242_99"): "BinOutput/Talk/GadgetGroup/4242_99.json",
    }


def test_talk_collision_dedupes_identical_resolved_text() -> None:
    """Different hashes are duplicate content when they resolve to the same text."""
    parser = talk_parsing.TalkParser.__new__(talk_parsing.TalkParser)
    parser.talk_id_to_path = {}
    parser._talk_candidates = {
        42: [
            "BinOutput/Talk/Quest/42.json",
            "BinOutput/Talk/Quest/8dc4251a.json",
        ]
    }
    data_repo = mock.Mock(spec=repo.DataRepo)
    data_repo.text_map_tracker.return_value = repo.TextMapTracker(
        {"100": "Same", "101": "Same", "200": "Tail", "201": "Tail"},
        localization.Language.ENG,
        pronoun_hashes={},
    )
    data_repo.load_talk_data.side_effect = lambda path: {
        "BinOutput/Talk/Quest/42.json": {
            "dialogList": [
                {"id": 1, "talkContentTextMapHash": 100},
                {"id": 2, "talkContentTextMapHash": 200},
            ]
        },
        "BinOutput/Talk/Quest/8dc4251a.json": {
            "dialogList": [
                {"id": 1, "talkContentTextMapHash": 101},
                {"id": 2, "talkContentTextMapHash": 201},
            ]
        },
    }[path]

    parser._resolve_talk_candidates(data_repo, {})

    assert parser.talk_id_to_path[42] == "BinOutput/Talk/Quest/42.json"


def test_talk_collision_prefers_resolved_text_superset() -> None:
    """A fuller candidate can win even when ids and hashes were remapped."""
    parser = talk_parsing.TalkParser.__new__(talk_parsing.TalkParser)
    parser.talk_id_to_path = {}
    parser._talk_candidates = {
        42: [
            "BinOutput/Talk/Quest/42.json",
            "BinOutput/Talk/Npc/42.json",
        ]
    }
    data_repo = mock.Mock(spec=repo.DataRepo)
    data_repo.text_map_tracker.return_value = repo.TextMapTracker(
        {"100": "Start", "101": "Start", "200": "Only fuller"},
        localization.Language.ENG,
        pronoun_hashes={},
    )
    data_repo.load_talk_data.side_effect = lambda path: {
        "BinOutput/Talk/Quest/42.json": {
            "dialogList": [{"id": 1, "talkContentTextMapHash": 100}]
        },
        "BinOutput/Talk/Npc/42.json": {
            "dialogList": [
                {"id": 9, "talkContentTextMapHash": 101},
                {"id": 10, "talkContentTextMapHash": 200},
            ]
        },
    }[path]

    parser._resolve_talk_candidates(data_repo, {})

    assert parser.talk_id_to_path[42] == "BinOutput/Talk/Npc/42.json"
