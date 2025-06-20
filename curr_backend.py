from flask import Flask, request, jsonify
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import subprocess
import tempfile
import json
import datetime
import re

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
You are a world-class Senior QA Automation Engineer. Your task is to analyze a recorded user session (Playwright JS file) and a desired functionality to test, and then create a comprehensive list of test case ideas.

**CONTEXT:**
- **User Journey (from JS File):** I will provide a sequence of actions a user took on a website (e.g., Login -> Fill Form 1 -> Fill Form 2 -> Logout).
- **Functionality to Test:** The user will specify a part of that journey they want to test thoroughly (e.g., "Form 1").

**YOUR TASK:**
1.  **Understand the Test Flow:** Your primary goal is to generate test cases for the *specific functionality* requested.
2.  **Isolate the Target:** Treat all steps in the JS file *before* the target functionality as a necessary "setup." For example, if the user wants to test "Form 1", the "Login" part of the JS file is the setup. You do not need to generate test cases for the setup itself.
3.  **Generate Specific & Creative Test Ideas:** For the specified functionality, generate a list of both positive and negative test case titles. These should be creative and cover common edge cases.

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

Generate up to 15 relevant test case titles based on these instructions.
"""

    try:
        response = llm.invoke(prompt)
        # Extract JSON from response
        json_start = response.content.find('{')
        json_end = response.content.rfind('}') + 1
        json_str = response.content[json_start:json_end]
        
        test_ideas = json.loads(json_str).get("test_ideas", [])
        return jsonify({"test_ideas": test_ideas[:15]})
    except Exception as e:
        return jsonify({"error": f"Failed to parse test ideas: {str(e)}"}), 500

@app.route("/generate_script", methods=["POST"])
def generate_script():
    data = request.get_json()
    js_file_content = data.get("js_file_content", "")
    selected_tests = data.get("selected_tests", [])
    website_url = data.get("website_url", "")

    prompt = f"""
You are a senior QA automation engineer. Generate a Playwright Python pytest script with the following STRICT requirements:

1. **Imports and Fixtures:**  
   Use these imports and fixtures exactly:
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

2. **Test Structure:**  
   - Each test function (`def test_...`) must be fully self-contained.  
   - Each test must start from `page.goto({website_url})` and perform all necessary steps (login, navigation, etc.) to reach the target functionality, using the actions and locators from the provided JS file.
   - Do not share state between tests.

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
           # After clicking, check that the DOM of the relevant form has not changed:
           form = page.locator('form-selector')  # Use the actual form selector from the JS file
           before = form.inner_html()
           submit_button.click()
           after = form.inner_html()
           assert before == after
     - Do **not** use `expect()` on strings or HTML content.
     - Do **not** check for specific error messages or invent selectors.
     - Use only locators and actions present in the JS file.
   - **For form-related negative test cases (e.g., 'don't fill age and test submit')**: All other fields in the form should be filled with valid data as per the JS file, except the one being tested for negative behavior. This ensures the test is consistent and only the intended field is left empty or invalid.
   - **For dropdowns:** Select a valid option for positive tests, and for negative tests, try not selecting any option or selecting an invalid option if possible.
   - **For checkboxes/radio buttons:** For positive tests, check the required boxes; for negative, leave them unchecked or select conflicting options if applicable.
   - **For file uploads:** For positive, upload a valid file; for negative, try uploading an invalid file type or leave it empty.
   - **For search or filter functionalities:** For positive, enter a valid search term and assert results appear; for negative, enter an invalid or empty term and assert no results or an appropriate message.
   - **For navigation or multi-step forms:** Always follow the correct flow as per the JS file to reach the target step, and for each test, only alter the specific field or action under test.

4. **Test Naming:**  
   - Name each test function clearly based on the test case description.

5. **No Markdown or Explanations:**  
   - Output only the raw Python code, no markdown fences or extra text.

6. **Inputs:**  
   - Website URL: {website_url}
   - JS file actions (for setup and locators):  
     ```javascript
     {js_file_content}
     ```
   - Test cases to generate:  
     {selected_tests}

Follow these rules strictly. Do not invent selectors, URLs, or error messages. Use only what is present in the JS file and the test case descriptions.
"""

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
    

@app.route("/run_script", methods=["POST"])
def run_script():
    data = request.get_json()
    script_content = data.get("script_content", "")

    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = os.path.join(temp_dir, "test_script.py")
        report_path = os.path.join(temp_dir, "report.json")

        with open(script_path, "w") as f:
            f.write(script_content)

        try:
            # Run pytest with json reporting
            cmd = [
                "pytest", 
                script_path,
                "--json-report",
                f"--json-report-file={report_path}",
                "--capture=no"
            ]
            subprocess.run(cmd, check=False, cwd=temp_dir, capture_output=True, text=True)

            # Parse and format results for frontend
            if not os.path.exists(report_path):
                return jsonify({
                    "error": "Test execution failed",
                    "details": "No report generated - possible syntax error"
                }), 400

            with open(report_path) as f:
                report = json.load(f)

            logs = []
            for test in report.get("tests", []):
                logs.append({
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "action": test.get("nodeid", "Unknown Test"),
                    "result": test.get("outcome", "error").capitalize()
                })
                # Add individual test steps if available
                for call in test.get("call", {}).get("trace", {}).get("steps", []):
                    logs.append({
                        "timestamp": datetime.datetime.fromtimestamp(call["start"]).strftime("%Y-%m-%d %H:%M:%S"),
                        "action": call["name"],
                        "result": "Pass" if call["status"] == "passed" else "Fail"
                    })

            return jsonify({"logs": logs})

        except Exception as e:
            return jsonify({
                "error": "Test execution failed",
                "details": str(e)
            }), 500
    





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



