from flask import Flask, request, jsonify
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import subprocess
import tempfile
import json
import datetime
import re

import logging
# ──────────────────────────────────────────
# one-time logger setup – put near top-of-file
logging.basicConfig(
    filename="test_runner.log",           # <— central log file
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)
# ─────────────────

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-05-20",
    temperature=0.2,
    api_key=os.getenv("GOOGLE_API_KEY")
)

app = Flask(__name__)

def clean_llm_output(text):
    """Removes markdown code fences and other artifacts from LLM output."""
    text = re.sub(r'^```python\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'```$', '', text, flags=re.MULTILINE)
    return text.strip()

@app.route("/generate_test_ideas", methods=["POST"])
def generate_test_ideas():
    data = request.get_json()
    js_file_content = data.get("js_file_content", "")
    functionality = data.get("functionality", "")

    prompt = f"""
You are a world-class Senior QA Automation Engineer. Your task is to analyze a recorded user session (Playwright JS file) and a desired functionality to test, and then create a comprehensive list of test case ideas pay attention to the JS file comments and understand if sections are present .

**CONTEXT:**
- **User Journey (from JS File):** I will provide a sequence of actions a user took on a website (e.g., Login -> Fill Form 1 -> Fill Form 2 -> Logout).
- **Functionality to Test:** The user will specify a part of that journey they want to test thoroughly (e.g., "Form 1").

**YOUR TASK:**
1.  **Understand the Test Flow:** Your primary goal is to generate as many logical and non-overlapping test cases for the *specific functionality* requested.
2.  **Isolate the Target:** Treat all steps in the JS file *before* the target functionality as a necessary "setup." For example, if the user wants to test "Form 1", the "Login" part of the JS file is the setup. You do not need to generate test cases for the setup itself.
3.  **Generate Specific & Creative Test Ideas:** For the specified functionality, generate a list of both positive and negative test case titles. These should be creative and cover common edge cases.
4.  **If the number of test cases is mentioned in the prompt then generate that exact amount of test cases**
**STRICT OUTPUT FORMAT:**
Return ONLY a JSON object like this. Do not include any other text, markdown, or explanations.
{{
    "test_ideas": [
        "Test Case Title 1",
        "Test Case Title 2",
        ...
    ]
}}


**EXAMPLES OF GOOD TEST IDEAS:**

*   **If the user asks to test "Login":**
    *   "Test successful login with valid credentials"
    *   "Test login with valid username and invalid password"
    *   "Test login with invalid username and valid password"
    *   "Test login with empty username field"
    *   "Test login with empty password field"

*   **If the JS file shows a form and the user asks to test "the patient information form":**
    *   "Test successful form submission with all valid data"
    *   "Test submitting the form with an empty 'First Name' field"
    *   "Test submitting the form with a 'First Name' containing numbers or special characters"
    *   "Test submitting the form with an invalid Date of Birth (e.g., future date)"
    *   "Test submitting with a required checkbox unchecked"

**YOUR INPUTS:**

*   **Functionality to Test:** '{functionality}'
*   **User Journey JS File:**
    ```javascript
    {js_file_content}
    ```

**Additional Instructions:**
1. *Whole-Flow Mode*  
   • If the user request explicitly contains keywords like **"whole flow", "entire web-flow", "all sections"** or if *no functionality* is provided, assume they want to test every section of the journey.  
   • Break the journey into logical sections by reading the JS file **comments** (e.g., `// Login`, `// Form-1`).  
   • Generate **up to 5** creative test-idea titles for **each incremental slice** of the flow.  Using `Login → Form-1 → Form-2` as an example you must return:  
       – 5 ideas that validate *Login* alone.  
       – 5 ideas for *Login then Form-1*.  
       – 5 ideas for *Login then Form-1 then Form-2*.  
   • Make sure the titles make it obvious which slice they belong to (e.g., "[Login Only] ...").

2. *Verbatim-Flow / Sanity Mode*  
   • If the user says **"convert JS to pytest", "run recorded flow", "one sanity test"** or similar, return **exactly one** idea: `"Execute the recorded flow end-to-end without deviations"`.

3. *Focused Functionality Mode* (default)  
   • If a specific functionality string is supplied (e.g., "Signup"), generate ideas **only for that section**, treating all preceding steps in the JS file as *setup*.

4. *Edge-Case Comments*  
   • Sometimes comments mention optional UI elements (e.g., a floating chat widget after login).  If such an element appears **it should merely be clicked/closed and the flow must continue**; do not turn it into a separate test idea.

5. *Negative Test Case Isolation*  
   • For negative test ideas involving a specific field (e.g., "empty age", "invalid email"), assume all other fields are filled with valid data as per the JS file. Do not suggest test ideas where multiple fields are invalid at once unless that is a realistic user scenario.

Always respect the recorded selectors and never invent URLs or error messages.
"""

    try:
        response = llm.invoke(prompt)
        # Extract JSON from response
        json_start = response.content.find('{')
        json_end = response.content.rfind('}') + 1
        json_str = response.content[json_start:json_end]
        
        test_ideas = json.loads(json_str).get("test_ideas", [])
        return jsonify({"test_ideas": test_ideas})
    except Exception as e:
        return jsonify({"error": f"Failed to parse test ideas: {str(e)}"}), 500

@app.route("/generate_script", methods=["POST"])
def generate_script():
    data = request.get_json()
    js_file_content = data.get("js_file_content", "")
    selected_tests = data.get("selected_tests", [])
    website_url = data.get("website_url", "")
    test_ideas = data.get("test_ideas", [])

    prompt = """
            You are a senior QA automation engineer. Generate a Playwright Python pytest script with the following STRICT requirements pay attention to the JS file comments
            you may need to use the comments to handle edge cases , and make dedicated pytest functions to ensure a smooth flow of the test cases

1. **Imports and Fixtures:**  
   Use these imports and fixtures exactly:
   import pytest
   from playwright.sync_api import sync_playwright, expect
   from datetime import datetime

   @pytest.fixture(scope="session")
   def browser():
       with sync_playwright() as p:
           browser = p.chromium.launch(headless=False,slow_mo=1000)
           yield browser
           browser.close()

   @pytest.fixture
   def page(browser):
       page = browser.new_page()
       yield page
       page.close()

2. **Test Structure:**  
   - Each test function (`def test_...`) must be fully self-contained.  
   - Each test must start from `page.goto({website_url})` and perform all necessary steps (login, navigation, etc.) to reach the target functionality, using the actions and locators from the provided JS file.
   - Do not share state between tests.

**CRITICAL PLAYWRIGHT SYNTAX:** 
   -Eg: 
   - Viewport: `page.set_viewport_size({{"width": 1280, "height": 720}})` NOT `page.set_viewport_size(width=1280, height=720)`
   - Wait for element: `page.wait_for_selector("selector")` NOT `page.wait_for_element("selector")`
   - Fill input: `page.locator("input").fill("text")` NOT `page.locator("input").type("text")`
   - Click and wait: `page.locator("button").click()` then `page.wait_for_load_state()`

3. **Test Logic:**  
   - For **positive** test cases:  
     - After the final action, assert that the URL has changed (i.e., navigation occurred) using:
       initial_url = page.url
       # ... perform actions ...
       with page.expect_navigation():
           page.locator(...).click()
       expect(page).not_to_have_url(initial_url)

   - For **negative** login or form test cases (e.g., invalid form submission, invalid login):  
     - First, check if the submit/next/login button is disabled:
       submit_button = page.locator("...")
       if submit_button.is_disabled():
           expect(submit_button).to_be_disabled()
       else:
           initial_url = page.url
           submit_button.click()
           # After clicking, check that the URL did not change, the next expected element in the flow is NOT visible, and the current form fields/buttons are still visible:
           expect(page).to_have_url(initial_url)
           # Replace the selector below with the next expected element in the flow (e.g., dashboard, confirmation, or next form)
           expect(page.locator("<next-element-selector>")).not_to_be_visible()
           # Assert that the current form fields/buttons are still visible (replace selectors as per JS file)
           expect(page.locator('[data-testid="username"]').to_be_visible()
           expect(page.locator('[data-testid="password"]').to_be_visible()
           expect(submit_button).to_be_visible()
     - Do **not** use `expect()` on strings or HTML content.
     - Do **not** check for specific error messages or invent selectors. Only check for error messages if a selector/class is provided in the JS file.
     - Do **not** perform full DOM string comparisons.
     - Use only locators and actions present in the JS file.

   - **For form-related negative test cases:**
     - When testing a negative scenario for a specific field (e.g., "age" is invalid), all other fields in the form must be filled with valid data as per the JS file. Only the field under test should be invalid or empty. Do not create negative tests where multiple fields are invalid unless that is a realistic user scenario.

   - **For dropdowns, checkboxes, file uploads, search/filter, navigation, etc.:** (as previously described...)

4. **Whole-Flow Testing (Incremental):**  
   - When the user requests keywords like *"whole flow"*, *"entire web-flow"*, or leaves the functionality blank, break the JS journey into clearly marked **sections** using its comments.  
   - Produce incremental tests: e.g., `Login only`, `Login + Form-1`, `Login + Form-1 + Form-2`, each set containing up to **5 tests**.  
   - Re-use the same **setup code** for the prerequisite steps so that each test starts from the home page and reaches the required slice.

5. **Verbatim-Flow / Sanity Test (Single):**  
   - When the user says *"convert JS to pytest"*, *"run recorded JS flow"*, *"sanity"*, etc., create **exactly one** test function that reproduces the recorded JS actions **verbatim** (step-by-step, using only the actions and selectors from the JS file). Do **not** add intermediate assertions. Only add a single assertion at the end of the test, such as checking the final URL or that a final element (present at the end of the JS flow) is visible. Do not invent selectors or error messages.

6. **Edge-Case Elements:**  
   - If optional/pop-up UI elements (e.g., chat widgets) appear as indicated by JS comments, handle them gracefully (`if page.locator("text=Chat").is_visible(): ...`) but **do not** assert their presence or fail because of them.

7. **Test Naming:**  
    - Name each test function clearly based on the test case description.

8. **No Markdown or Explanations:**  
    - Output only the raw Python code, no markdown fences or extra text.

9. **Inputs:**  
   - Website URL: {website_url}
   - JS file actions (for setup and locators):  
     ```javascript
     {js_file_content}
     ```
   - Test cases to generate:  
     {selected_tests}
   - User request: {test_ideas}

Follow these rules strictly. Do not invent selectors, URLs, or error messages. Use only what is present in the JS file and the test case descriptions.
""".format(
        website_url=website_url,
        js_file_content=js_file_content,
        selected_tests=selected_tests,
        test_ideas=test_ideas
    )

    try:
        response = llm.invoke(prompt)

        script = clean_llm_output(response.content)
        # Loosened validation: only require fixtures and imports
        required = [
            "@pytest.fixture",
            "def page(",
            "def browser(",
            "import pytest",
            "from playwright.sync_api import sync_playwright, expect",
            "from datetime import datetime"
        ]
        if not all(x in script for x in required):
            print("Generated script:\n", script)  # Log for debugging
            raise ValueError("Generated script missing required fixtures or imports")
        return jsonify({"script": script})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# @app.route("/run_script", methods=["POST"])
# def run_script():
#     data = request.get_json()
#     script_content = data.get("script_content", "")

#     with tempfile.TemporaryDirectory() as temp_dir:
#         script_path = os.path.join(temp_dir, "test_script.py")
#         report_path = os.path.join(temp_dir, "report.json")

#         with open(script_path, "w") as f:
#             f.write(script_content)

#         try:
#             # Run pytest with json reporting
#             cmd = [
#                 "pytest", 
#                 script_path,
#                 "--json-report",
#                 f"--json-report-file={report_path}",
#                 "--capture=no"
#             ]
#             subprocess.run(cmd, check=False, cwd=temp_dir, capture_output=True, text=True)

#             # Parse and format results for frontend
#             if not os.path.exists(report_path):
#                 return jsonify({
#                     "error": "Test execution failed",
#                     "details": "No report generated - possible syntax error"
#                 }), 400

#             with open(report_path) as f:
#                 report = json.load(f)

#             logs = []
#             passed = failed = 0

#             for test in report.get("tests", []):
#                 outcome = test.get("outcome", "error")
#                 if outcome == "passed":
#                     reason = "Test passed successfully."
#                 else:
#                     # Extract failure reason from 'longrepr'
#                     longrepr = test.get("longrepr", "")
#                     if isinstance(longrepr, dict):
#                         # Try multiple nested fields
#                         reason = (
#                             longrepr.get("reprcrash", {}).get("message")
#                             or longrepr.get("message")
#                             or longrepr.get("reprtraceback", {}).get("entries", [{}])[-1].get("line")
#                             or json.dumps(longrepr)
#                         )
#                     else:
#                         reason = str(longrepr) if longrepr else "Unknown error"
#                 logs.append({
#                     "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                     "action": test.get("nodeid", "Unknown Test"),
#                     "result": outcome.capitalize(),
#                     "reason": reason
#                 })

#                 if outcome == "passed":
#                     passed += 1
#                 else:
#                     failed += 1

#                 # Optional: detailed step trace (does not affect stats)
#                 for call in test.get("call", {}).get("trace", {}).get("steps", []):
#                     logs.append({
#                         "timestamp": datetime.datetime.fromtimestamp(call["start"]).strftime("%Y-%m-%d %H:%M:%S"),
#                         "action": call["name"],
#                         "result": "Pass" if call["status"] == "passed" else "Fail",
#                         "reason": ""
#                     })

#             return jsonify({
#                 "logs": logs,
#                 "stats": {
#                     "passed": passed,
#                     "failed": failed,
#                     "total": passed + failed
#                 }
#             })

#         except Exception as e:
#             return jsonify({
#                 "error": "Test execution failed",
#                 "details": str(e)
#             }), 500
    

@app.route("/run_script", methods=["POST"])
def run_script():
    data = request.get_json()
    script_content = data.get("script_content", "").strip()

    if not script_content:
        return jsonify({"error": "Empty script_content"}), 400

    with tempfile.TemporaryDirectory() as temp_dir:
        script_path  = os.path.join(temp_dir, "test_script.py")
        report_path  = os.path.join(temp_dir, "report.json")

        # write the script to disk
        with open(script_path, "w") as f:
            f.write(script_content)

        # ── run pytest and capture *all* terminal output ────────────────────────
        cmd = [
            "pytest",
            script_path,
            "--json-report",
            f"--json-report-file={report_path}",
            "--capture=no",
        ]
        result = subprocess.run(
            cmd,
            cwd=temp_dir,
            text=True,
            capture_output=True,   # stdout+stderr captured here
        )

        # always log raw terminal output
        logger.info("[pytest stdout]\n%s", result.stdout.strip())
        logger.info("[pytest stderr]\n%s", result.stderr.strip())

        # decide up-front whether something failed
        pytest_failed = result.returncode != 0
        json_report_missing = not os.path.exists(report_path)

        # if *anything* failed, dump the generated script for later debugging
        if pytest_failed or json_report_missing:
            logger.error("[generated test_script.py]\n%s", script_content)

        # ── graceful HTTP responses ───────────────────────────────────────────
        if json_report_missing:
            return jsonify({
                "error": "Test execution failed",
                "details": "No JSON report generated – check logs for full traceback"
            }), 500

        # normal happy-path: parse report, build stats
        with open(report_path) as f:
            report = json.load(f)

        logs   = []
        passed = failed = 0

        for test in report.get("tests", []):
            outcome  = test.get("outcome", "error")
            nodeid   = test.get("nodeid", "Unknown Test")
            longrepr = test.get("longrepr", "")
            reason   = "Test passed successfully."

            if outcome != "passed":
                failed += 1
                # human-readable failure reason
                if isinstance(longrepr, dict):
                    reason = (
                        longrepr.get("reprcrash", {}).get("message")
                        or longrepr.get("message")
                        or json.dumps(longrepr)[:300]  # trim if massive
                    )
                else:
                    reason = str(longrepr)[:300]
            else:
                passed += 1

            logs.append({
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": nodeid,
                "result": outcome.capitalize(),
                "reason": reason,
            })

        return jsonify({
            "logs": logs,
            "stats": {
                "passed": passed,
                "failed": failed,
                "total": passed + failed,
            },
            # optional: echo temp_dir for inspection in dev mode
            # "tmp": temp_dir
        })



if __name__ == "__main__":
    app.run(debug=True, port=5000)



# @app.route("/run_script", methods=["POST"])
# def run_script():
#     data = request.get_json()
#     script_content = data.get("script_content", "")

#     # Validate script content
#     if not script_content.strip():
#         return jsonify({
#             "error": "Empty script",
#             "logs": [{
#                 "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                 "action": "Script validation",
#                 "result": "Error"
#             }],
#             "stats": {"passed": 0, "failed": 0, "total": 0}
#         }), 400

#     with tempfile.TemporaryDirectory() as temp_dir:
#         script_path = os.path.join(temp_dir, "test_script.py")
#         report_path = os.path.join(temp_dir, "report.json")

#         with open(script_path, "w") as f:
#             f.write(script_content)

#         try:
#             cmd = [
#                 "pytest", 
#                 script_path,
#                 "--json-report",
#                 f"--json-report-file={report_path}",
#                 "--capture=no"
#             ]
#             result = subprocess.run(cmd, check=False, cwd=temp_dir, capture_output=True, text=True)

#             # Handle execution errors
#             if result.returncode != 0:
#                 error_logs = [{
#                     "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                     "action": line.strip(),
#                     "result": "Error"
#                 } for line in result.stderr.split('\n') if line.strip()]
                
#                 if not error_logs:
#                     error_logs.append({
#                         "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                         "action": "Unknown execution error",
#                         "result": "Error"
#                     })

#                 return jsonify({
#                     "error": "Test execution failed",
#                     "logs": error_logs,
#                     "stats": {"passed": 0, "failed": 0, "total": 0}
#                 })

#             # Parse results
#             with open(report_path) as f:
#                 report = json.load(f)

#             logs = []
#             passed = failed = 0
#             for test in report.get("tests", []):
#                 outcome = test.get("outcome", "error")
#                 result_details = {
#                     "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                     "action": test.get("nodeid", "Unknown Test"),
#                     "result": outcome.capitalize(),
#                     "reason": "Test passed successfully."
#                 }

#                 if outcome == "passed":
#                     passed += 1
#                 else:
#                     failed += 1
#                     # Extract failure reason from the 'longrepr' field if it exists
#                     result_details["reason"] = test.get("longrepr", "No failure reason available.")
                
#                 logs.append(result_details)

#             return jsonify({
#                 "logs": logs,
#                 "stats": {
#                     "passed": passed,
#                     "failed": failed,
#                     "total": passed + failed
#                 }
#             })

#         except Exception as e:
#             return jsonify({
#                 "error": "Test execution failed",
#                 "logs": [{
#                     "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                     "action": str(e),
#                     "result": "Error"
#                 }],
#                 "stats": {"passed": 0, "failed": 0, "total": 0}
#             }), 500


