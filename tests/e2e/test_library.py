"""Library browse and search flows."""

import re
from typing import Any

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_browse_to_document(page: Page, sample_library_file: dict[str, Any]) -> None:
    page.goto("/library")
    expect(page.get_by_role("heading", name="提瓦特图书馆")).to_be_visible(
        timeout=60_000
    )
    expect(page.locator("button[aria-expanded]").first).to_be_visible()

    page.get_by_placeholder("按标题筛选...").fill(sample_library_file["title"])
    page.get_by_role("button", name=sample_library_file["title"]).first.click()

    expect(page).to_have_url(
        re.compile(
            rf"/library/{re.escape(sample_library_file['category'])}"
            rf"/{sample_library_file['file_id']}"
        )
    )
    expect(page.get_by_role("button", name="复制分享链接")).to_be_visible()
    expect(page.get_by_role("button", name="返回文件列表")).to_be_visible()


def test_library_search(page: Page) -> None:
    page.goto("/library")
    search_box = page.get_by_placeholder("输入文本以查找相关文档")
    expect(search_box).to_be_visible(timeout=60_000)
    search_box.fill("风神巴巴托斯")
    page.get_by_role("button", name="搜索", exact=True).click()

    results = page.locator("article")
    expect(results.first).to_be_visible(timeout=60_000)
    results.first.get_by_role("link").first.click()
    expect(page).to_have_url(re.compile(r"/library/[^/]+/\d+"))
    expect(page.get_by_role("button", name="返回文件列表")).to_be_visible()
