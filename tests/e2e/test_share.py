"""Short-URL sharing flow."""

import re
from typing import Any

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_share_short_url(page: Page, sample_library_file: dict[str, Any]) -> None:
    path = (
        f"/library/{sample_library_file['category']}/{sample_library_file['file_id']}"
    )
    page.goto(path)
    share_button = page.get_by_role("button", name="复制分享链接")
    expect(share_button).to_be_visible(timeout=60_000)

    # The button creates the short URL before copying; capture the slug from the
    # API response rather than the clipboard (headless clipboard is unreliable).
    with page.expect_response("**/api/short-urls") as response_info:
        share_button.click()
    slug = response_info.value.json()["slug"]

    page.goto(f"/s/{slug}")
    expect(page).to_have_url(re.compile(re.escape(path)))
    expect(page.get_by_role("button", name="返回文件列表")).to_be_visible(
        timeout=60_000
    )
