"""Shared test fixtures."""

import os

import pytest

from istaroth import utils
from istaroth.agd import repo


@pytest.fixture
def agd_path() -> str:
    """Get AGD path from environment variable."""
    agd_path_value = os.environ.get("AGD_PATH")
    if not agd_path_value:
        pytest.skip("AGD_PATH environment variable not set")
    return utils.assert_not_none(agd_path_value)


@pytest.fixture
def data_repo() -> repo.DataRepo:
    """Create DataRepo instance from environment."""
    try:
        return repo.DataRepo.from_env()
    except ValueError:
        pytest.skip("AGD_PATH environment variable not set")
        # This line will never be reached due to pytest.skip() raising an exception
        # but mypy doesn't understand that, so we need a return statement
        raise  # pragma: no cover
