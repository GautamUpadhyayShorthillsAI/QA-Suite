import pytest
from playwright.sync_api import sync_playwright, expect
from datetime import datetime, timedelta

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

def _login_and_handle_new_chat(page):
    page.goto('https://geneconnectdoctor.shorthills.ai/login')
    page.click('[data-testid="username"]')
    page.fill('[data-testid="username"]', "test123")
    page.click('[data-testid="password"]')
    page.fill('[data-testid="password"]', "testpass")
    
    with page.expect_navigation():
        page.click('[data-testid="submit_button"]')
    
    # Check if "New Chat" button is visible and click it
    new_chat_button = page.locator('.hover\\:bg-accent')
    if new_chat_button.is_visible():
        with page.expect_navigation():
            new_chat_button.click()

def _fill_first_form_valid_data(page, first_name="abhinav", last_name="arvind", dob_str="01/01/1990", gender_male=True):
    page.fill('#P\\.firstName', first_name)
    page.fill('#P\\.lastName', last_name)
    page.fill('#P\\.dob', dob_str)
    page.press('#P\\.dob', 'Enter') # Ensure date input is registered
    if gender_male:
        page.click('#P\\.gender-male')

def _assert_first_form_negative(page, submit_button_locator):
    submit_button = page.locator(submit_button_locator)
    if submit_button.is_disabled():
        expect(submit_button).to_be_disabled()
    else:
        initial_url = page.url
        submit_button.click()
        expect(page).to_have_url(initial_url)
        expect(page.locator('#P\\.firstName')).to_be_visible()
        expect(page.locator('#P\\.lastName')).to_be_visible()
        expect(page.locator('#P\\.dob')).to_be_visible()
        expect(page.locator('#P\\.gender-male')).to_be_visible() # Check one of the gender options
        expect(submit_button).to_be_visible()

def test_successful_submission_of_first_form_with_all_valid_data(page):
    _login_and_handle_new_chat(page)
    
    initial_url = page.url
    
    # Fill First Form
    _fill_first_form_valid_data(page, dob_str="01/01/1990")
    
    # Click Next
    with page.expect_navigation():
        page.locator('.h-9').click()
    
    # Fill Medical History for First Form
    page.click('#P\\.medicalHistory\\.diabetes')
    page.click('#P\\.medicalHistory\\.hypertension')
    page.click('#P\\.medicalHistory\\.cancer')
    page.click('#P\\.medicalHistory\\.heartDisease')
    
    # Click Save and Continue
    with page.expect_navigation():
        page.locator('.h-9').click()
    
    expect(page).not_to_have_url(initial_url)

def test_first_form_submission_with_empty_first_name_field(page):
    _login_and_handle_new_chat(page)
    
    # Fill First Form with empty First Name
    _fill_first_form_valid_data(page, first_name="", last_name="arvind", dob_str="01/01/1990", gender_male=True)
    
    # Click Next
    _assert_first_form_negative(page, '.h-9')

def test_first_form_submission_with_empty_last_name_field(page):
    _login_and_handle_new_chat(page)
    
    # Fill First Form with empty Last Name
    _fill_first_form_valid_data(page, first_name="abhinav", last_name="", dob_str="01/01/1990", gender_male=True)
    
    # Click Next
    _assert_first_form_negative(page, '.h-9')

def test_first_form_submission_with_date_of_birth_set_to_a_future_date(page):
    _login_and_handle_new_chat(page)
    
    # Set DOB to a future date (e.g., 1 year from now)
    future_date = (datetime.now() + timedelta(days=365)).strftime("%m/%d/%Y")
    _fill_first_form_valid_data(page, first_name="abhinav", last_name="arvind", dob_str=future_date, gender_male=True)
    
    # Click Next
    _assert_first_form_negative(page, '.h-9')

def test_first_form_submission_with_date_of_birth_indicating_an_age_below_a_reasonable_minimum(page):
    _login_and_handle_new_chat(page)
    
    # Set DOB to today's date (age < 1 year)
    today_date = datetime.now().strftime("%m/%d/%Y")
    _fill_first_form_valid_data(page, first_name="abhinav", last_name="arvind", dob_str=today_date, gender_male=True)
    
    # Click Next
    _assert_first_form_negative(page, '.h-9')

def test_first_form_submission_without_selecting_a_gender(page):
    _login_and_handle_new_chat(page)
    
    # Fill First Form without selecting gender
    _fill_first_form_valid_data(page, first_name="abhinav", last_name="arvind", dob_str="01/01/1990", gender_male=False)
    
    # Click Next
    _assert_first_form_negative(page, '.h-9')

def test_first_form_submission_with_first_name_containing_invalid_characters(page):
    _login_and_handle_new_chat(page)
    
    # Fill First Name with invalid characters
    _fill_first_form_valid_data(page, first_name="abhinav123!", last_name="arvind", dob_str="01/01/1990", gender_male=True)
    
    # Click Next
    _assert_first_form_negative(page, '.h-9')

def test_first_form_submission_with_date_of_birth_for_a_very_old_person(page):
    _login_and_handle_new_chat(page)
    
    # Set DOB to a very old date (e.g., 1900)
    very_old_date = "01/01/1900"
    _fill_first_form_valid_data(page, first_name="abhinav", last_name="arvind", dob_str=very_old_date, gender_male=True)
    
    # Click Next
    _assert_first_form_negative(page, '.h-9')