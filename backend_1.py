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
You are a QA expert. Based on this Playwright JS file and the '{functionality}' functionality, 
generate exactly 20 test case titles in this STRICT JSON format in case there are more than 20 test cases for a particular functionality. 
If the user explicitly asks for a specific number of test cases for a particular functionality, then only generate that number of test cases:
Also finally as an example if a user specifies a particular functionality like form filling and validation , then only generate test cases for that functionality and keep the flow till that functionality same as the JS file 
For eg: If i have asked you to test a particular form filling , but that form appears after Login , then till we reach that form or any other functionality on the website just go with the flow of the JS file and stop at that functionality and test that functionality with the required test cases 
Eg 2: Now if a user wants to just test Login , then you just test the Login functionality and not move forward with any other functionality 

{{
    "test_ideas": [
        "Test 1 description",
        "Test 2 description",
        ...
    ]
}}

JS File:
```javascript
{js_file_content}
```

Guidelines for test ideas:
- Only generate test ideas that are relevant to the specified functionality and the actions in the JS file.
- Do not generate test ideas that require verifying specific error messages unless a selector/class is provided.
- Focus on user flows, field validation, button state (enabled/disabled), and navigation.
- Avoid test ideas that require hardcoded error text or popups.
-Often there can be cases for example in a login page , if the user has kept an empty username or password  
then the Login/Submit button often does not work even after clicking it and as a consequence we don't shift to the next URL or page 
so we need to check for that and assert that the URL has not changed or check whether the Login/Submit button is disabled or not.
This can be in the cases of forms as well where the user has not filled all the fields and the submit/Next button is disabled.

Return ONLY the JSON object with the test_ideas array. No other text or explanation.
"""

    try:
        response = llm.invoke(prompt)
        # Extract JSON from response
        json_start = response.content.find('{')
        json_end = response.content.rfind('}') + 1
        json_str = response.content[json_start:json_end]
        
        test_ideas = json.loads(json_str).get("test_ideas", [])
        if(len(test_ideas) < 20):
            return jsonify({"test_ideas":test_ideas})
        else:
            return jsonify({"test_ideas": test_ideas[:20]})  # Ensure exactly 20
    except Exception as e:
        return jsonify({"error": f"Failed to parse test ideas: {str(e)}"}), 500

@app.route("/generate_script", methods=["POST"])
def generate_script():
    data = request.get_json()
    js_file_content = data.get("js_file_content", "")
    selected_tests = data.get("selected_tests", [])
    website_url = data.get("website_url", "")

    prompt = f"""Generate a Python Playwright pytest script with these STRICT requirements:

1. IMPORTS (must include exactly):
```python
import pytest
import re
from playwright.sync_api import sync_playwright, expect
from datetime import datetime
```

2. FIXTURES (must include exactly):
```python
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
```

3. TEST STRUCTURE (each test must follow these rules):
- Use explicit locators from the recorded JS file for all actions (clicks, fills, etc.). Do not invent locators.

- For POSITIVE test cases (e.g., successful login, valid submission):
  - Only perform actions and assertions that are present in the recorded JS file. Do not guess URLs, elements, or success messages.
  - If the JS file shows navigation, check that the URL has changed (but do not hardcode a new URL).

- For NEGATIVE test cases (e.g., submitting an invalid form, missing required fields):
#   - First, check if the submit/next/login button is disabled when required fields are empty or invalid. If so, assert that the button is disabled and do not attempt to click it.
  - If the button is enabled and clicked, check that the URL does not change (i.e., the user is not navigated away).indicating that the fields are incorrect and the user is not able to proceed to the next page.
  - Don't assumes which URL's will appear try to check the URL's currently  if you are using it as check for the fields being incorrect and the user is not able to proceed to the next page.
  - Only check for error messages if a specific selector or class is provided (e.g., '.text-destructive'). Never invent error text or popups.
  - Do not assert on the presence of specific error messages unless instructed with a selector/class.

- Note: Websites may use inline error messages, disabled buttons, or other UI patterns to indicate errors. Adapt the test logic accordingly and avoid hallucinating UI elements or behaviors.
- Also finally if For eg: If i have asked you to test a particular form filling , but that form appears after Login , then till we reach that form or any other functionality on the website just go with the flow of the JS file 
  and stop at that functionality and test that functionality with the required test cases , once executed the test case , then continue with the other test cases and go with a similar flow as the JS file
  Eg 2: Now if a user wants to just test Login , then you just test the Login functionality and not move forward with any other functionality 

4. For website: {website_url}
5. Based on these recorded actions:
```javascript
{js_file_content}
```

6. Generate tests for:
{selected_tests}

7. Output ONLY the raw Python code
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
            "import re",
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
#             for test in report.get("tests", []):
#                 logs.append({
#                     "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
#                     "action": test.get("nodeid", "Unknown Test"),
#                     "result": test.get("outcome", "error").capitalize()
#                 })
#                 # Add individual test steps if available
#                 for call in test.get("call", {}).get("trace", {}).get("steps", []):
#                     logs.append({
#                         "timestamp": datetime.datetime.fromtimestamp(call["start"]).strftime("%Y-%m-%d %H:%M:%S"),
#                         "action": call["name"],
#                         "result": "Pass" if call["status"] == "passed" else "Fail"
#                     })

#             return jsonify({"logs": logs})

#         except Exception as e:
#             return jsonify({
#                 "error": "Test execution failed",
#                 "details": str(e)
#             }), 500



