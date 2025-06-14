import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        yield browser
        browser.close()

def test_enter_without_text(browser):
    page = browser.new_page()
    page.goto("https://www.google.com/")
    page.set_viewport_size({"width": 1920, "height": 966})
    page.press("#APjFqb", "Enter")
    page.wait_for_load_state("networkidle")
    assert "search" in page.url or "google.com" in page.url
    page.close()

def test_valid_search(browser):
    page = browser.new_page()
    page.goto("https://www.google.com/")
    page.set_viewport_size({"width": 1920, "height": 966})
    page.fill("#APjFqb", "Playwright testing")
    page.press("#APjFqb", "Enter")
    page.wait_for_load_state("networkidle")
    assert "Playwright" in page.title() or "playwright" in page.content().lower()
    page.close()

def test_missing_selector(browser):
    page = browser.new_page()
    page.goto("https://www.google.com/")
    with pytest.raises(Exception):
        page.press("#wrong-selector", "Enter")
    page.close()

def test_without_focusing_search(browser):
    page = browser.new_page()
    page.goto("https://www.google.com/")
    # Try pressing Enter on body (no focus)
    page.press("body", "Enter")
    assert "google.com" in page.url
    page.close()
