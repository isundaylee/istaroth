"""Tests for AGD talk collision parsing."""

from unittest import mock

from istaroth.agd import localization, repo, talk_parsing


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
    data_repo.load_text_map.return_value = repo.TextMapTracker(
        {"100": "Same", "101": "Same", "200": "Tail", "201": "Tail"},
        localization.Language.ENG,
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
    data_repo.load_text_map.return_value = repo.TextMapTracker(
        {"100": "Start", "101": "Start", "200": "Only fuller"},
        localization.Language.ENG,
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
