"""Fixtures for browser e2e tests against a running dev stack.

The suite requires an explicit target: ``ISTAROTH_E2E_URL``, or the
``.dev-stack.env`` written by ``scripts/dev-compose.sh setup``. With
``--run-e2e`` a missing or unreachable stack is a failure, not a skip.
"""

import os
import pathlib
from typing import Any

import httpx
import pytest

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def base_url() -> str:
    """Stack base URL; overrides pytest-base-url's fixture so `page.goto` is relative."""
    if url := os.environ.get("ISTAROTH_E2E_URL"):
        return url.rstrip("/")
    dev_stack_env = _REPO_ROOT / ".dev-stack.env"
    if not dev_stack_env.exists():
        pytest.fail(
            "--run-e2e needs ISTAROTH_E2E_URL or .dev-stack.env "
            "(run scripts/dev-compose.sh setup && scripts/dev-compose.sh up --detach)"
        )
    for line in dev_stack_env.read_text().splitlines():
        if line.startswith("CONDUCTOR_PORT="):
            return f"http://localhost:{line.removeprefix('CONDUCTOR_PORT=')}"
    pytest.fail(f"{dev_stack_env} has no CONDUCTOR_PORT")


@pytest.fixture(scope="session", autouse=True)
def _require_chs_stack(base_url: str) -> None:
    """Fail fast unless the stack is up and serves the CHS corpus (the UI default)."""
    try:
        resp = httpx.get(f"{base_url}/api/version", timeout=30)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        pytest.fail(f"dev stack not reachable at {base_url}: {e}")
    if "CHS" not in resp.json()["checkpoint_versions"]:
        pytest.fail("e2e suite drives the UI in CHS but the stack serves no CHS corpus")


@pytest.fixture(scope="session")
def sample_library_file(base_url: str) -> dict[str, Any]:
    """First titled leaf document in the library hierarchy, for browse/share flows."""
    resp = httpx.get(
        f"{base_url}/api/library/hierarchy", params={"language": "CHS"}, timeout=60
    )
    resp.raise_for_status()
    for entry in resp.json()["categories"]:
        stack = list(entry["nodes"])
        while stack:
            node = stack.pop(0)
            if node["file_id"] is not None and node["title"]:
                return {
                    "category": entry["category"],
                    "file_id": node["file_id"],
                    "title": node["title"],
                }
            stack = list(node["children"] or []) + stack
    pytest.fail("library hierarchy has no titled documents")
