"""Tests for AGD processing functionality."""

from istorath.agd import processing
from istorath.agd import repo


def test_book100_metadata(data_repo: repo.DataRepo) -> None:
    """Test retrieving metadata for Book100.txt."""
    readable_path = "Readable/CHS/Book100.txt"
    expected_title = "神霄折戟录·第六卷"
    
    metadata = processing.get_readable_metadata(readable_path, data_repo=data_repo)
    
    assert metadata.title == expected_title


def test_weapon11101_metadata(data_repo: repo.DataRepo) -> None:
    """Test retrieving metadata for Weapon11101.txt."""
    readable_path = "Readable/CHS/Weapon11101.txt"
    expected_title = "无锋剑"
    
    metadata = processing.get_readable_metadata(readable_path, data_repo=data_repo)
    
    assert metadata.title == expected_title