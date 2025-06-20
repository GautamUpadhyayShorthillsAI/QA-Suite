import pytest
import re
from playwright.sync_api import sync_playwright, expect
from datetime import datetime

# FIXTURES (must include exactly)
@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()

# Base URL for the tests
BASE_URL = "https://geneconnectdoctor.shorthills.ai/login"

# Helper function to handle the "New Chat" button if it appears
def handle_new_chat_button(page):
    new_chat_button_locator = page.locator('button.inline-flex.items-center.justify-center.whitespace-nowrap.rounded-md.text-sm.font-medium.transition-colors.focus-visible\:outline-none.focus-visible\:ring-1.focus-visible\:ring-ring.disabled\:opacity-50.disabled\:cursor-not-allowed.border.border-input.bg-background.shadow-sm.hover\:bg-accent.hover\:text-accent-foreground.h-9.px-4.py-2.mt-2.sm\:mt-0')
    if new_chat_button_locator.is_visible():
        new_chat_button_locator.click()

# Test Cases

def test_successful_login_and_full_flow(page):
    """Verify successful login with valid credentials navigates to the dashboard and completes the full recorded flow."""
    page.goto(BASE_URL)
    page.set_viewport_size({"width": 1850, "height": 966})

    # Store initial URL for later comparison
    initial_url = page.url

    # Click on <input> [data-testid="username"]
    page.click('[data-testid="username"]')
    # Fill "test123" on <input> [data-testid="username"]
    page.fill('[data-testid="username"]', "test123")

    # Click on <input> [data-testid="password"]
    page.click('[data-testid="password"]')
    # Fill "testpass" on <input> [data-testid="password"]
    page.fill('[data-testid="password"]', "testpass")

    # Click on <button> "Submit" and wait for navigation
    submit_button = page.locator('[data-testid="submit_button"]')
    with page.expect_navigation():
        submit_button.click()
    
    # Assert URL has changed (positive test case)
    expect(page).not_to_have_url(initial_url)

    # Handle "New Chat" button if visible
    handle_new_chat_button(page)

    # Click on <input> #P\.firstName
    page.click('#P\\.firstName')
    # Fill "Abhinav" on <input> #P\.firstName
    page.fill('#P\\.firstName', "Abhinav")

    # Click on <input> #P\.lastName
    page.click('#P\\.lastName')
    # Fill "Arvind" on <input> #P\.lastName
    page.fill('#P\\.lastName', "Arvind")

    # Click on <input> #P\.dob
    page.click('#P\\.dob')
    # Fill "09/07/2003" on <input> #P\.dob
    page.fill('#P\\.dob', "09/07/2003")

    # Click on <input> #P\.age (no fill action recorded)
    page.click('#P\\.age')

    # Click on <button> #P\.gender-male
    page.click('#P\\.gender-male')

    # Click on <button> #P\.isAdopted-Unknown
    page.click('#P\\.isAdopted-Unknown')

    # Click on <button> "Next"
    page.click('.h-9')

    # Click on <button> #P\.medicalHistory\.diabetes
    page.click('#P\\.medicalHistory\\.diabetes')

    # Click on <button> #P\.medicalHistory\.asthma
    page.click('#P\\.medicalHistory\\.asthma')

    # Click on <button> "Save and Continue"
    page.click('.h-9')

    # Click on <button> "Logout"
    page.click('.hover\\:bg-primary')

    # Click on <button> "Confirm" and wait for navigation
    confirm_logout_button = page.locator('.inline-flex:nth-child(2)')
    with page.expect_navigation():
        confirm_logout_button.click()

    # Assert navigation back to login page after logout
    expect(page).to_have_url(BASE_URL)


def test_login_empty_username(page):
    """Verify login attempt with an empty username field prevents navigation or disables submit button."""
    page.goto(BASE_URL)
    page.set_viewport_size({"width": 1850, "height": 966})
    initial_url = page.url

    # Click on <input> [data-testid="password"]
    page.click('[data-testid="password"]')
    # Fill "testpass" on <input> [data-testid="password"]
    page.fill('[data-testid="password"]', "testpass")
    # Username field is left empty

    submit_button = page.locator('[data-testid="submit_button"]')

    # Check if button is disabled first
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        # If not disabled, click and assert no navigation
        submit_button.click()
        expect(page).to_have_url(initial_url)


def test_login_empty_password(page):
    """Verify login attempt with an empty password field prevents navigation or disables submit button."""
    page.goto(BASE_URL)
    page.set_viewport_size({"width": 1850, "height": 966})
    initial_url = page.url

    # Click on <input> [data-testid="username"]
    page.click('[data-testid="username"]')
    # Fill "test123" on <input> [data-testid="username"]
    page.fill('[data-testid="username"]', "test123")
    # Password field is left empty

    submit_button = page.locator('[data-testid="submit_button"]')

    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        expect(page).to_have_url(initial_url)


def test_login_empty_username_and_password(page):
    """Verify login attempt with both username and password fields empty prevents navigation or disables submit button."""
    page.goto(BASE_URL)
    page.set_viewport_size({"width": 1850, "height": 966})
    initial_url = page.url

    # Both username and password fields are left empty

    submit_button = page.locator('[data-testid="submit_button"]')

    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        expect(page).to_have_url(initial_url)


def test_login_invalid_username_valid_password(page):
    """Verify login attempt with an invalid username and valid password prevents navigation to the dashboard."""
    page.goto(BASE_URL)
    page.set_viewport_size({"width": 1850, "height": 966})
    initial_url = page.url

    # Click on <input> [data-testid="username"]
    page.click('[data-testid="username"]')
    # Fill "invaliduser" on <input> [data-testid="username"]
    page.fill('[data-testid="username"]', "invaliduser")

    # Click on <input> [data-testid="password"]
    page.click('[data-testid="password"]')
    # Fill "testpass" on <input> [data-testid="password"]
    page.fill('[data-testid="password"]', "testpass")

    submit_button = page.locator('[data-testid="submit_button"]')

    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        expect(page).to_have_url(initial_url)


def test_login_valid_username_invalid_password(page):
    """Verify login attempt with a valid username and invalid password prevents navigation to the dashboard."""
    page.goto(BASE_URL)
    page.set_viewport_size({"width": 1850, "height": 966})
    initial_url = page.url

    # Click on <input> [data-testid="username"]
    page.click('[data-testid="username"]')
    # Fill "test123" on <input> [data-testid="username"]
    page.fill('[data-testid="username"]', "test123")

    # Click on <input> [data-testid="password"]
    page.click('[data-testid="password"]')
    # Fill "invalidpass" on <input> [data-testid="password"]
    page.fill('[data-testid="password"]', "invalidpass")

    submit_button = page.locator('[data-testid="submit_button"]')

    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        expect(page).to_have_url(initial_url)


def test_login_invalid_username_and_password(page):
    """Verify login attempt with both invalid username and invalid password prevents navigation to the dashboard."""
    page.goto(BASE_URL)
    page.set_viewport_size({"width": 1850, "height": 966})
    initial_url = page.url

    # Click on <input> [data-testid="username"]
    page.click('[data-testid="username"]')
    # Fill "invaliduser" on <input> [data-testid="username"]
    page.fill('[data-testid="username"]', "invaliduser")

    # Click on <input> [data-testid="password"]
    page.click('[data-testid="password"]')
    # Fill "invalidpass" on <input> [data-testid="password"]
    page.fill('[data-testid="password"]', "invalidpass")

    submit_button = page.locator('[data-testid="submit_button"]')

    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        submit_button.click()
        expect(page).to_have_url(initial_url)


def test_login_elements_visible_on_page_load(page):
    """Verify all required login form elements (username, password fields, submit button) are visible on page load."""
    page.goto(BASE_URL)
    page.set_viewport_size({"width": 1850, "height": 966})

    # Assert visibility of elements using explicit locators from JS
    expect(page.locator('[data-testid="username"]')).to_be_visible()
    expect(page.locator('[data-testid="password"]')).to_be_visible()
    expect(page.locator('[data-testid="submit_button"]')).to_be_visible()