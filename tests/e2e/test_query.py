"""The core ask-a-question flow: query stream, citations, and permalink."""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

# Fixed so reruns against the same stack hit the backend query cache instead of
# paying for another LLM generation.
_QUESTION = "钟离的真实身份是什么？"


def test_ask_question(page: Page) -> None:
    page.goto("/")
    page.get_by_role("textbox").fill(_QUESTION)

    # Cheapest retrieval preset to bound the first (uncached) run.
    page.get_by_role("button", name="检索深度").click()
    page.get_by_role("option", name="精简").click()

    submit = page.get_by_role("button", name="提问")
    expect(submit).to_be_enabled(timeout=30_000)
    submit.click()

    page.wait_for_url("**/conversation/**", timeout=300_000)
    expect(page.get_by_role("heading", name="回答")).to_be_visible()
    expect(page.get_by_role("heading", name="引用文献")).to_be_visible()

    # Inline citation marker opens the source popup.
    page.locator("sup[data-citation-id]").first.click()
    expect(page.get_by_role("button", name="关闭").first).to_be_visible()

    # The conversation permalink reloads from the database.
    conversation_url = page.url
    page.goto(conversation_url)
    expect(page.get_by_text(_QUESTION)).to_be_visible(timeout=60_000)
    expect(page.get_by_role("heading", name="回答")).to_be_visible()
