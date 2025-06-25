import pytest
from playwright.sync_api import sync_playwright, expect
from datetime import datetime

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,slow_mo=500)
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()

# Helper function for login
def login(page):
    page.set_viewport_size({"width": 1280, "height": 720})
    page.goto('https://geneconnectdoctor.shorthills.ai/login', timeout=7000)
    page.wait_for_selector('[data-testid="username"]', timeout=7000)
    page.locator('[data-testid="username"]').fill("test123", timeout=7000)
    page.locator('[data-testid="password"]').fill("testpass", timeout=7000)
    
    initial_url = page.url
    page.locator('[data-testid="submit_button"]').click(timeout=7000)
    page.wait_for_load_state(timeout=7000) # Wait for network idle or DOM content loaded
    
    # Check if navigation occurred after login
    if page.url != initial_url:
        # Navigation occurred, login successful
        pass
    else:
        # If URL did not change, check if the login button is no longer visible or a new element appears
        if not page.locator('[data-testid="submit_button"]').is_visible(timeout=7000):
            pass
        else:
            pytest.fail("Login failed: Expected navigation or UI change did not occur.")

# Helper function to handle the optional "New Chat" button
def handle_new_chat_button(page):
    # This is the locator you need to click if a new chat button appears on the screen 
    new_chat_button_selector = '.hover\:bg-accent'
    if page.locator(new_chat_button_selector).is_visible(timeout=7000):
        page.locator(new_chat_button_selector).click(timeout=7000)
        page.wait_for_load_state(timeout=7000) # Wait for any potential load after clicking new chat

# Helper function to fill the first form with valid data
def fill_first_form_valid_data(page):
    page.wait_for_selector('#P\\.firstName', timeout=7000) # Ensure form is loaded
    page.locator('#P\\.firstName').fill("Abhinav", timeout=7000)
    page.locator('#P\\.lastName').fill("Arvind", timeout=7000)
    page.locator('#P\\.dob').fill("09/07/2003", timeout=7000) # dd/mm/yyyy
    page.locator('#P\\.age').click(timeout=7000) # As per JS, just click, not fill
    page.locator('#P\\.gender-male').click(timeout=7000)
    page.locator('#P\\.isAdopted-Unknown').click(timeout=7000)

# Test Cases

def test_successful_submission_first_form_valid_data(page):
    login(page)
    handle_new_chat_button(page)
    
    # First Form starts
    fill_first_form_valid_data(page)
    
    # Click on <button> "Next"
    next_button_selector = '.h-9'
    initial_url = page.url
    page.locator(next_button_selector).click(timeout=7000)
    page.wait_for_load_state(timeout=7000) # Wait for any potential load after clicking next

    # Apply positive test case assertion logic
    if page.url != initial_url:
        assert True
    else:
        if not page.locator(next_button_selector).is_visible(timeout=7000):
            assert True
        # Optionally, check if the next expected element (e.g., a medical history field) is visible
        elif page.locator('#P\\.medicalHistory\\.diabetes').is_visible(timeout=7000):
            assert True
        else:
            assert False, "Expected navigation or UI change did not occur after valid first form submission."

def test_first_form_submission_empty_age_field(page):
    login(page)
    handle_new_chat_button(page)
    
    # First Form starts - fill all fields except age
    page.wait_for_selector('#P\\.firstName', timeout=7000)
    page.locator('#P\\.firstName').fill("Abhinav", timeout=7000)
    page.locator('#P\\.lastName').fill("Arvind", timeout=7000)
    page.locator('#P\\.dob').fill("09/07/2003", timeout=7000) # dd/mm/yyyy
    # DO NOT interact with #P.age for this test
    page.locator('#P\\.gender-male').click(timeout=7000)
    page.locator('#P\\.isAdopted-Unknown').click(timeout=7000)
    
    # Click on <button> "Next"
    next_button_selector = '.h-9'
    submit_button = page.locator(next_button_selector)

    # Apply negative test case assertion logic
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        initial_url = page.url
        submit_button.click(timeout=7000)
        page.wait_for_load_state(timeout=7000) # Wait for any potential load after clicking next
        
        if page.url == initial_url:
            assert submit_button.is_visible(timeout=7000)
            # Optionally, check that key fields are still visible, e.g., first name
            assert page.locator('#P\\.firstName').is_visible(timeout=7000)
            # No specific error message selector provided in JS for this case.
        else:
            assert False, "Unexpected navigation occurred on invalid input (empty age)."

def test_first_form_submission_without_selecting_gender(page):
    login(page)
    handle_new_chat_button(page)
    
    # First Form starts - fill all fields except gender
    page.wait_for_selector('#P\\.firstName', timeout=7000)
    page.locator('#P\\.firstName').fill("Abhinav", timeout=7000)
    page.locator('#P\\.lastName').fill("Arvind", timeout=7000)
    page.locator('#P\\.dob').fill("09/07/2003", timeout=7000) # dd/mm/yyyy
    page.locator('#P\\.age').click(timeout=7000) # As per JS, just click, not fill
    # DO NOT select gender
    page.locator('#P\\.isAdopted-Unknown').click(timeout=7000)
    
    # Click on <button> "Next"
    next_button_selector = '.h-9'
    submit_button = page.locator(next_button_selector)

    # Apply negative test case assertion logic
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        initial_url = page.url
        submit_button.click(timeout=7000)
        page.wait_for_load_state(timeout=7000)
        
        if page.url == initial_url:
            assert submit_button.is_visible(timeout=7000)
            assert page.locator('#P\\.gender-male').is_visible(timeout=7000) # Ensure gender options are still visible
        else:
            assert False, "Unexpected navigation occurred on invalid input (no gender selected)."

def test_first_form_submission_invalid_date_of_birth_format(page):
    login(page)
    handle_new_chat_button(page)
    
    # First Form starts - fill all fields, but with invalid DOB format
    page.wait_for_selector('#P\\.firstName', timeout=7000)
    page.locator('#P\\.firstName').fill("Abhinav", timeout=7000)
    page.locator('#P\\.lastName').fill("Arvind", timeout=7000)
    page.locator('#P\\.dob').fill("09-07-2003", timeout=7000) # Invalid format: MM-DD-YYYY instead of dd/mm/yyyy
    page.locator('#P\\.age').click(timeout=7000)
    page.locator('#P\\.gender-male').click(timeout=7000)
    page.locator('#P\\.isAdopted-Unknown').click(timeout=7000)
    
    # Click on <button> "Next"
    next_button_selector = '.h-9'
    submit_button = page.locator(next_button_selector)

    # Apply negative test case assertion logic
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        initial_url = page.url
        submit_button.click(timeout=7000)
        page.wait_for_load_state(timeout=7000)
        
        if page.url == initial_url:
            assert submit_button.is_visible(timeout=7000)
            assert page.locator('#P\\.dob').is_visible(timeout=7000) # Ensure DOB field is still visible
        else:
            assert False, "Unexpected navigation occurred on invalid input (invalid DOB format)."

def test_first_form_submission_date_of_birth_in_future(page):
    login(page)
    handle_new_chat_button(page)
    
    # First Form starts - fill all fields, but with DOB in future
    future_date = (datetime.now().year + 1).strftime("%d/%m/%Y") # e.g., 09/07/2025
    
    page.wait_for_selector('#P\\.firstName', timeout=7000)
    page.locator('#P\\.firstName').fill("Abhinav", timeout=7000)
    page.locator('#P\\.lastName').fill("Arvind", timeout=7000)
    page.locator('#P\\.dob').fill(future_date, timeout=7000)
    page.locator('#P\\.age').click(timeout=7000)
    page.locator('#P\\.gender-male').click(timeout=7000)
    page.locator('#P\\.isAdopted-Unknown').click(timeout=7000)
    
    # Click on <button> "Next"
    next_button_selector = '.h-9'
    submit_button = page.locator(next_button_selector)

    # Apply negative test case assertion logic
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        initial_url = page.url
        submit_button.click(timeout=7000)
        page.wait_for_load_state(timeout=7000)
        
        if page.url == initial_url:
            assert submit_button.is_visible(timeout=7000)
            assert page.locator('#P\\.dob').is_visible(timeout=7000) # Ensure DOB field is still visible
        else:
            assert False, "Unexpected navigation occurred on invalid input (DOB in future)."