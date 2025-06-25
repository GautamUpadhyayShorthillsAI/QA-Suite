import pytest
from playwright.sync_api import sync_playwright, expect

# Test credentials
VALID_EMAIL = "test3"
VALID_PASSWORD = "value@123"
INVALID_EMAIL = "wrong@example.com"
INVALID_PASSWORD = "wrongpass"
VERIFICATION_CODE = ["9", "9", "9", "9", "9"]
WRONG_VERIFICATION_CODE = ["1", "2", "3", "4", "5"]


def login(page, email, password, check_remember=True):
    page.goto("https://valueinsightpro.jumpiq.com/auth/login?redirect=/")
    page.set_viewport_size({"width": 1920, "height": 966})
    page.fill('[data-testid="company-email-input"]', email)
    page.fill('[data-testid="password-input"]', password)
    if check_remember:
        page.click(".ant-checkbox-input")
    page.click("button")
    page.wait_for_load_state("networkidle")


def enter_verification_code(page, code_list):
    selectors = [
        ".ant-input-compact-first-item",
        ".ant-input:nth-child(2)",
        ".ant-input:nth-child(3)",
        ".ant-input:nth-child(4)",
        ".ant-input-compact-last-item",
    ]
    for selector, code in zip(selectors, code_list):
        page.fill(selector, code)
    page.click(".ant-btn-default")
    page.wait_for_load_state("networkidle")


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        yield browser
        browser.close()


def test_valid_login_and_report_flow(browser):
    page = browser.new_page()
    login(page, VALID_EMAIL, VALID_PASSWORD)
    enter_verification_code(page, VERIFICATION_CODE)
    page.click(".card:nth-child(1) > .overlay")
    page.click("#home_screen_new_val_drop_down")
    page.click(".ant-select-item-option-active > .ant-select-item-option-content")
    page.click("text=Next")
    page.wait_for_load_state("networkidle")
    page.click("text=Exit")
    page.wait_for_load_state("networkidle")
    page.close()


def test_invalid_login(browser):
    page = browser.new_page()
    login(page, INVALID_EMAIL, INVALID_PASSWORD)
    assert "Invalid" in page.content() or page.url.endswith("/auth/login?redirect=/")
    page.close()


def test_blank_login(browser):
    page = browser.new_page()
    login(page, "", "")
    assert "required" in page.content().lower()
    page.close()


def test_wrong_verification_code(browser):
    page = browser.new_page()
    login(page, VALID_EMAIL, VALID_PASSWORD)
    enter_verification_code(page, WRONG_VERIFICATION_CODE)
    assert "invalid" in page.content().lower() or "error" in page.content().lower()
    page.close()


def test_without_selecting_dealer(browser):
    page = browser.new_page()
    login(page, VALID_EMAIL, VALID_PASSWORD)
    enter_verification_code(page, VERIFICATION_CODE)
    page.click(".card:nth-child(1) > .overlay")
    page.click("text=Next")  # Without selecting
    assert "select" in page.content().lower()
    page.close()
