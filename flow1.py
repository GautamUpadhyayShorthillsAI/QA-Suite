import pytest
import re
from playwright.sync_api import sync_playwright, expect
from datetime import datetime

# 1. IMPORTS (must include exactly):
# (Already included above)

# 2. FIXTURES (must include exactly):
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

# Base URL for the application
BASE_URL = "https://geneconnectdoctor.shorthills.ai/login"

# Helper function to navigate to the login page and set viewport
def navigate_to_login_page(page):
    """Navigates to the login page and sets the viewport size as per the JS recording."""
    page.goto(BASE_URL)
    page.set_viewport_size({"width": 1850, "height": 966})

# 3. TEST CASES

def test_successful_login(page):
    """Verify successful login with valid username and password."""
    navigate_to_login_page(page)

    # Store the initial URL to verify navigation
    initial_url = page.url

    # Fill "test123" on <input> [data-testid="username"]
    page.fill('[data-testid="username"]', "test123")

    # Fill "testpass" on <input> [data-testid="password"]
    page.fill('[data-testid="password"]', "testpass")

    # Locate the submit button
    submit_button = page.locator('[data-testid="submit_button"]')

    # For a positive test case, the submit button should be enabled
    expect(submit_button).to_be_enabled()

    # Click on <button> "Submit" and wait for navigation
    # The JS recording shows page.waitForNavigation() after clicking submit.
    with page.expect_navigation():
        submit_button.click()

    # Assert URL has changed, indicating successful navigation
    # Do not hardcode the new URL, just check it's different from the initial login URL.
    expect(page).not_to_have_url(initial_url)

    # As per the requirement: "if a user wants to just test Login , then you just test the Login functionality and not move forward with any other functionality"
    # Therefore, we stop here and do not proceed with patient form filling or logout actions from the JS recording.

def test_login_fails_invalid_username(page):
    """Verify login fails with an invalid username."""
    navigate_to_login_page(page)

    # Store the initial URL to verify no navigation
    initial_url = page.url

    # Fill invalid username
    page.fill('[data-testid="username"]', "invalid_user")
    # Fill valid password
    page.fill('[data-testid="password"]', "testpass")

    # Locate the submit button
    submit_button = page.locator('[data-testid="submit_button"]')

    # Assume the button remains enabled for invalid credentials but doesn't navigate.
    # If the button were disabled, the test would assert that and not click.
    expect(submit_button).to_be_enabled()

    # Click on <button> "Submit"
    submit_button.click()

    # Assert URL does not change, indicating login failure
    expect(page).to_have_url(initial_url)
    # No assertion on specific error messages as no selector was provided in the JS recording or requirements.

def test_login_fails_invalid_password(page):
    """Verify login fails with an invalid password."""
    navigate_to_login_page(page)

    # Store the initial URL to verify no navigation
    initial_url = page.url

    # Fill valid username
    page.fill('[data-testid="username"]', "test123")
    # Fill invalid password
    page.fill('[data-testid="password"]', "invalid_pass")

    # Locate the submit button
    submit_button = page.locator('[data-testid="submit_button"]')

    # Assume the button remains enabled for invalid credentials but doesn't navigate.
    expect(submit_button).to_be_enabled()

    # Click on <button> "Submit"
    submit_button.click()

    # Assert URL does not change, indicating login failure
    expect(page).to_have_url(initial_url)
    # No assertion on specific error messages as no selector was provided in the JS recording or requirements.

def test_login_fails_empty_username(page):
    """Verify login fails when the username field is left empty."""
    navigate_to_login_page(page)

    # Store the initial URL to verify no navigation
    initial_url = page.url

    # Leave username empty
    page.fill('[data-testid="username"]', "")
    # Fill valid password
    page.fill('[data-testid="password"]', "testpass")

    # Locate the submit button
    submit_button = page.locator('[data-testid="submit_button"]')

    # As per requirements for negative tests: "First, check if the submit/next/login button is disabled when required fields are empty or invalid. If so, assert that the button is disabled and do not attempt to click it."
    expect(submit_button).to_be_disabled()
    # Do not attempt to click the button if it's disabled.

    # Assert URL does not change (it shouldn't, as the button is disabled)
    expect(page).to_have_url(initial_url)
    # No assertion on specific error messages as no selector was provided in the JS recording or requirements.

def test_login_fails_empty_password(page):
    """Verify login fails when the password field is left empty."""
    navigate_to_login_page(page)

    # Store the initial URL to verify no navigation
    initial_url = page.url

    # Fill valid username
    page.fill('[data-testid="username"]', "test123")
    # Leave password empty
    page.fill('[data-testid="password"]', "")

    # Locate the submit button
    submit_button = page.locator('[data-testid="submit_button"]')

    # Check if the submit button is disabled
    expect(submit_button).to_be_disabled()
    # Do not attempt to click the button if it's disabled.

    # Assert URL does not change
    expect(page).to_have_url(initial_url)
    # No assertion on specific error messages as no selector was provided in the JS recording or requirements.

def test_login_fails_empty_both(page):
    """Verify login fails when both username and password fields are left empty."""
    navigate_to_login_page(page)

    # Store the initial URL to verify no navigation
    initial_url = page.url

    # Leave both fields empty
    page.fill('[data-testid="username"]', "")
    page.fill('[data-testid="password"]', "")

    # Locate the submit button
    submit_button = page.locator('[data-testid="submit_button"]')

    # Check if the submit button is disabled
    expect(submit_button).to_be_disabled()
    # Do not attempt to click the button if it's disabled.

    # Assert URL does not change
    expect(page).to_have_url(initial_url)
    # No assertion on specific error messages as no selector was provided in the JS recording or requirements.