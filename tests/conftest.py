"""Shared test fixtures."""

import os

import pytest

from istorath.agd import repo


@pytest.fixture
def agd_path() -> str:
    """Get AGD path from environment variable."""
    agd_path_value = os.environ.get("AGD_PATH")
    if not agd_path_value:
        pytest.skip("AGD_PATH environment variable not set")
    return agd_path_value


@pytest.fixture
def data_repo(agd_path: str) -> repo.DataRepo:
    """Create DataRepo instance."""
    return repo.DataRepo(agd_path)
