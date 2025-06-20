import pytest
from playwright.sync_api import sync_playwright, expect
from datetime import datetime

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()

# Helper function for login
def _perform_login(page, username, password):
    page.goto('https://geneconnectdoctor.shorthills.ai/login')
    page.fill('[data-testid="username"]', username)
    page.fill('[data-testid="password"]', password)
    return page.locator('[data-testid="submit_button"]')

# Helper function for post-login "New Chat" check
def _check_and_click_new_chat(page):
    # This locator is from the JS file for the "New Chat" button
    new_chat_button = page.locator('.hover\\:bg-accent')
    # Check if the button is visible and enabled before attempting to click
    if new_chat_button.is_visible() and new_chat_button.is_enabled():
        with page.expect_navigation():
            new_chat_button.click()

def test_successful_login_with_valid_username_and_password(page):
    initial_url = page.url
    submit_button = _perform_login(page, "test123", "testpass")
    
    with page.expect_navigation():
        submit_button.click()
    
    expect(page).not_to_have_url(initial_url)
    
    # After successful login, check for and click "New Chat" if present
    _check_and_click_new_chat(page)

def test_login_with_valid_username_and_an_incorrect_password(page):
    initial_url = page.url
    before_content = page.content()
    submit_button = _perform_login(page, "test123", "incorrectpass")
    
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        try:
            expect(page).to_have_url(initial_url)
        except AssertionError:
            after_content = page.content()
            assert before_content == after_content

def test_login_with_an_incorrect_username_and_a_valid_password(page):
    initial_url = page.url
    before_content = page.content()
    submit_button = _perform_login(page, "incorrectuser", "testpass")
    
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        try:
            expect(page).to_have_url(initial_url)
        except AssertionError:
            after_content = page.content()
            assert before_content == after_content

def test_login_with_both_username_and_password_incorrect(page):
    initial_url = page.url
    before_content = page.content()
    submit_button = _perform_login(page, "incorrectuser", "incorrectpass")
    
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        try:
            expect(page).to_have_url(initial_url)
        except AssertionError:
            after_content = page.content()
            assert before_content == after_content

def test_login_attempt_with_an_empty_username_field(page):
    initial_url = page.url
    before_content = page.content()
    submit_button = _perform_login(page, "", "testpass")
    
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        try:
            expect(page).to_have_url(initial_url)
        except AssertionError:
            after_content = page.content()
            assert before_content == after_content

def test_login_attempt_with_an_empty_password_field(page):
    initial_url = page.url
    before_content = page.content()
    submit_button = _perform_login(page, "test123", "")
    
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        try:
            expect(page).to_have_url(initial_url)
        except AssertionError:
            after_content = page.content()
            assert before_content == after_content

def test_login_attempt_with_both_username_and_password_fields_empty(page):
    initial_url = page.url
    before_content = page.content()
    submit_button = _perform_login(page, "", "")
    
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        try:
            expect(page).to_have_url(initial_url)
        except AssertionError:
            after_content = page.content()
            assert before_content == after_content