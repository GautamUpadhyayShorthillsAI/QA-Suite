import pytest
from playwright.sync_api import sync_playwright

# Test data
VALID_USERNAME = "test123"
VALID_PASSWORD = "testpass"
INVALID_USERNAME = "wronguser"
INVALID_PASSWORD = "wrongpass"

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=2000)
        yield browser
        browser.close()

def login(page, username, password):
    page.goto("https://geneconnectdoctor.shorthills.ai/login")
    page.set_viewport_size({"width": 1850, "height": 966})
    page.fill('[data-testid="username"]', username)
    page.fill('[data-testid="password"]', password)
    page.click('[data-testid="submit_button"]')
    page.wait_for_load_state('networkidle')

def fill_patient_info(page):
    page.fill('#P\\.firstName', "Abhinav")
    page.fill('#P\\.lastName', "Arvind")
    page.fill('#P\\.dob', "09/07/2003")
    page.click('#P\\.age')  # May auto-calculate
    page.click('#P\\.gender-male')
    page.click('#P\\.isAdopted-Unknown')
    page.click('.h-9')  # "Next"

def select_medical_history(page):
    page.click('#P\\.medicalHistory\\.diabetes')
    page.click('#P\\.medicalHistory\\.asthma')
    page.click('.h-9')  # "Save and Continue"

def logout(page):
    page.click('.hover\\:bg-primary')  # "Logout"
    page.click('.inline-flex:nth-child(2)')  # "Confirm"
    page.wait_for_load_state('networkidle')

def test_full_positive_flow(browser):
    page = browser.new_page()
    login(page, VALID_USERNAME, VALID_PASSWORD)
    fill_patient_info(page)
    select_medical_history(page)
    logout(page)
    page.close()

def test_invalid_login(browser):
    page = browser.new_page()
    login(page, INVALID_USERNAME, INVALID_PASSWORD)
    assert "invalid" in page.content().lower() or "error" in page.content().lower()
    page.close()

def test_blank_patient_info(browser):
    page = browser.new_page()
    login(page, VALID_USERNAME, VALID_PASSWORD)
    page.click('.h-9')  # Try to submit without filling
    assert "required" in page.content().lower() or "fill" in page.content().lower()
    page.close()

def test_invalid_dob(browser):
    page = browser.new_page()
    login(page, VALID_USERNAME, VALID_PASSWORD)
    page.fill('#P\\.firstName', "John")
    page.fill('#P\\.lastName', "Doe")
    page.fill('#P\\.dob', "invalid-date")
    page.click('#P\\.age')
    page.click('.h-9')
    assert "invalid" in page.content().lower()
    page.close()

def test_skip_medical_history(browser):
    page = browser.new_page()
    login(page, VALID_USERNAME, VALID_PASSWORD)
    fill_patient_info(page)
    page.click('.h-9')  # Submit without selecting conditions
    assert "select" in page.content().lower() or "required" in page.content().lower()
    page.close()