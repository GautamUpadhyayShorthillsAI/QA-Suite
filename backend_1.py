from flask import Flask, request, jsonify
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import subprocess
import tempfile
import json
import datetime
import re
import time
from utils.logger import (
    get_logger,
    log_info,
    log_error,
    log_api_call,
    log_performance,
    log_file_operation,
    log_test_result,
)

# Initialize logger for backend
logger = get_logger("Backend")

load_dotenv()

# Log backend startup
logger.info(
    "Starting QA-Suite Backend",
    python_version=os.sys.version,
    flask_version="2.3.3",
    langchain_version="0.1.53",
)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-05-20",
    temperature=0.2,
    api_key=os.getenv("GOOGLE_API_KEY"),
)

logger.info(
    "LLM initialized",
    model="gemini-2.5-flash-preview-05-20",
    temperature=0.2,
    api_key_configured=bool(os.getenv("GOOGLE_API_KEY")),
)

app = Flask(__name__)


def clean_llm_output(text):
    """Removes markdown code fences and other artifacts from LLM output."""
    logger.debug(
        "Cleaning LLM output", original_length=len(text), has_code_fences="```" in text
    )
    text = re.sub(r"^```python\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"```$", "", text, flags=re.MULTILINE)
    cleaned_text = text.strip()
    logger.debug(
        "LLM output cleaned",
        cleaned_length=len(cleaned_text),
        removed_chars=len(text) - len(cleaned_text),
    )
    return cleaned_text


@app.route("/generate_test_ideas", methods=["POST"])
def generate_test_ideas():
    start_time = time.time()
    logger.info("Received test ideas generation request")
    try:
        data = request.get_json()
        js_file_content = data.get("js_file_content", "")
        functionality = data.get("functionality", "")
        logger.info(
            "Processing test ideas request",
            functionality=functionality,
            js_content_length=len(js_file_content),
            has_js_content=bool(js_file_content),
        )
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


Guidelines for test ideas:

Only generate test ideas that are relevant to the specified functionality and the actions in the JS file.

Generate test cases for both the 'happy path' (successful submission) and 'negative paths' (e.g., submitting with each required field left empty one at a time).

Do not generate test ideas that require verifying specific error messages unless a selector/class is provided.

Focus on user flows, field validation, button state (enabled/disabled), and navigation.

Avoid test ideas that require hardcoded error text or popups.
-Often there can be cases for example in a login page , if the user has kept an empty username or password
then the Login/Submit button often does not work even after clicking it and as a consequence we don't shift to the next URL or page
so we need to check for that and assert that the URL has not changed or check whether the Login/Submit button is disabled or not.
This can be in the cases of forms as well where the user has not filled all the fields and the submit/Next button is disabled.

Return ONLY the JSON object with the test_ideas array. No other text or explanation.
"""
        logger.info("Calling LLM for test ideas generation")
        llm_start_time = time.time()
        response = llm.invoke(prompt)
        llm_duration = time.time() - llm_start_time
        logger.info(
            "LLM response received",
            response_length=len(response.content),
            llm_duration=llm_duration,
        )
        json_start = response.content.find("{")
        json_end = response.content.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            logger.error(
                "No JSON found in LLM response", response_preview=response.content[:200]
            )
            return jsonify({"error": "Invalid JSON response from LLM"}), 500
        json_str = response.content[json_start:json_end]
        logger.debug(
            "Extracted JSON from response",
            json_length=len(json_str),
            json_preview=json_str[:100],
        )
        test_ideas = json.loads(json_str).get("test_ideas", [])
        logger.info(
            "Test ideas generated successfully",
            test_ideas_count=len(test_ideas),
            ideas_preview=test_ideas[:3] if test_ideas else [],
        )
        if len(test_ideas) < 20:
            result = {"test_ideas": test_ideas}
        else:
            result = {"test_ideas": test_ideas[:20]}
        total_duration = time.time() - start_time
        log_performance(
            "generate_test_ideas",
            total_duration,
            test_ideas_count=len(result["test_ideas"]),
        )
        return jsonify(result)
    except json.JSONDecodeError as e:
        logger.error(
            "JSON parsing error",
            error=str(e),
            response_preview=(
                response.content[:200] if "response" in locals() else "No response"
            ),
        )
        return jsonify({"error": f"Failed to parse test ideas: {str(e)}"}), 500
    except Exception as e:
        logger.error(
            "Unexpected error in generate_test_ideas",
            error=str(e),
            error_type=type(e).__name__,
        )
        return jsonify({"error": f"Failed to generate test ideas: {str(e)}"}), 500


@app.route("/generate_script", methods=["POST"])
def generate_script():
    start_time = time.time()
    logger.info("Received script generation request")
    try:
        data = request.get_json()
        js_file_content = data.get("js_file_content", "")
        selected_tests = data.get("selected_tests", [])
        website_url = data.get("website_url", "")
        logger.info(
            "Processing script generation request",
            website_url=website_url,
            selected_tests_count=len(selected_tests),
            js_content_length=len(js_file_content),
            selected_tests_preview=selected_tests[:3] if selected_tests else [],
        )
        prompt = f"""Generate a Python Playwright pytest script with these STRICT requirements:
IMPORTS (must include exactly):
import pytest
import re
from playwright.sync_api import sync_playwright, expect
from datetime import datetime
FIXTURES (must include exactly):
@pytest.fixture(scope=\"session\")
def browser():
    with sync_playwright() as p:
        # IMPORTANT: Always launch with slow_mo=500 (or higher if needed for reliability)
        browser = p.chromium.launch(headless=False, slow_mo=500)
        yield browser
        browser.close()
@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()
TEST STRUCTURE (each test must follow these rules):
Use explicit locators from the recorded JS file for all actions (clicks, fills, etc.). Do not invent locators.
NEW RULE: When identifying elements, strongly prefer robust selectors like data-testid, id, or page.get_by_role('button', name='...'). If the recorded JS file only provides a generic CSS class selector (e.g., .h-9, .btn), add a comment in the generated code: # WARNING: The following selector is generic and may be unreliable.
NEW RULE: Do not make assumptions about element states like 'disabled' or 'read-only' unless the recorded JS file provides a direct basis for it. Prioritize asserting visibility and value over behavioral states you have to guess.
Every call to set_viewport_size must be of the form page.set_viewport_size({{"width": <int>, "height": <int>}})
Never use a selector string that contains unbalanced quotes (run " and ' counts must both be even). Reject the generation if this rule is broken.

# NEW RULES FOR RELIABILITY:
# 1. After every page.goto(...), IMMEDIATELY call page.wait_for_load_state('networkidle') to ensure the page is fully loaded before interacting with selectors.
# 2. After every click that is expected to cause navigation (e.g., login, submit, next), IMMEDIATELY call page.wait_for_load_state('networkidle') before proceeding to the next step.
# 3. Use slow_mo in browser launch as above to make all actions slower and more reliable for selector detection.

For POSITIVE test cases (e.g., successful login, valid submission):
UPDATED RULE: When asserting a successful navigation, the most reliable method is to expect a unique and stable element on the new page to be visible. Use URL checks as a secondary confirmation. Do not guess new URLs.
Only perform actions and assertions that are present in the recorded JS file.
For NEGATIVE test cases (e.g., submitting an invalid form, missing required fields):
First, check if the submit/next/login button is disabled when required fields are empty or invalid. If so, assert that the button is disabled and do not attempt to click it.
If the button is enabled and clicked, check that the URL does not change (i.e., the user is not navigated away).
Only check for error messages if a specific selector or class is provided (e.g., '.text-destructive'). Never invent error text or popups.
Note: Websites may use inline error messages, disabled buttons, or other UI patterns to indicate errors. Adapt the test logic accordingly and avoid hallucinating UI elements or behaviors.
Also finally if For eg: If i have asked you to test a particular form filling , but that form appears after Login , then till we reach that form or any other functionality on the website just go with the flow of the JS file
and stop at that functionality and test that functionality with the required test cases , once executed the test case , then continue with the other test cases and go with a similar flow as the JS file
Eg 2: Now if a user wants to just test Login , then you just test the Login functionality and not move forward with any other functionality
For website: {website_url}
Based on these recorded actions:
{js_file_content}
Generate tests for:
{selected_tests}
Output ONLY the raw Python code
"""
        logger.info("Calling LLM for script generation")
        llm_start_time = time.time()
        response = llm.invoke(prompt)
        llm_duration = time.time() - llm_start_time
        logger.info(
            "LLM response received for script generation",
            response_length=len(response.content),
            llm_duration=llm_duration,
        )
        script = clean_llm_output(response.content)
        logger.debug(
            "Script generated", script_length=len(script), script_preview=script[:200]
        )
        required = [
            "@pytest.fixture",
            "def page(",
            "def browser(",
            "import pytest",
            "import re",
            "from playwright.sync_api import sync_playwright, expect",
            "from datetime import datetime",
        ]
        missing_requirements = [req for req in required if req not in script]
        if missing_requirements:
            logger.error(
                "Generated script missing required components",
                missing_requirements=missing_requirements,
                script_preview=script[:500],
            )
            raise ValueError(
                f"Generated script missing required fixtures or imports: {missing_requirements}"
            )
        logger.info(
            "Script validation passed",
            script_length=len(script),
            has_fixtures=True,
            has_imports=True,
        )
        total_duration = time.time() - start_time
        log_performance(
            "generate_script",
            total_duration,
            script_length=len(script),
            tests_count=len(selected_tests),
        )
        return jsonify({"script": script})
    except Exception as e:
        logger.error(
            "Error in generate_script", error=str(e), error_type=type(e).__name__
        )
        return jsonify({"error": str(e)}), 500


@app.route("/run_script", methods=["POST"])
def run_script():
    start_time = time.time()
    logger.info("Received script execution request")
    try:
        data = request.get_json()
        script_content = data.get("script_content", "")
        logger.info(
            "Processing script execution",
            script_length=len(script_content),
            script_preview=script_content[:200],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "test_script.py")
            report_path = os.path.join(temp_dir, "report.json")
            detailed_log_path = os.path.join(temp_dir, "detailed_log.txt")
            logger.info(
                "Created temporary directory",
                temp_dir=temp_dir,
                script_path=script_path,
                report_path=report_path,
            )
            try:
                with open(script_path, "w") as f:
                    f.write(script_content)
                log_file_operation(
                    "write", script_path, True, content_length=len(script_content)
                )
            except Exception as e:
                logger.error(
                    "Failed to write script file", error=str(e), script_path=script_path
                )
                return jsonify({"error": f"Failed to write script: {str(e)}"}), 500
            try:
                cmd = [
                    "pytest",
                    script_path,
                    "--json-report",
                    f"--json-report-file={report_path}",
                    "--capture=no",
                    "-v",
                    "--tb=long",
                    f"--log-file={detailed_log_path}",
                    "--log-file-level=DEBUG",
                    "--log-cli-level=DEBUG",
                ]
                logger.info(
                    "Executing pytest command",
                    command=" ".join(cmd),
                    working_dir=temp_dir,
                )
                execution_start = time.time()
                result = subprocess.run(
                    cmd, check=False, cwd=temp_dir, capture_output=True, text=True
                )
                execution_duration = time.time() - execution_start
                logger.info(
                    "Pytest execution completed",
                    return_code=result.returncode,
                    execution_duration=execution_duration,
                    stdout_length=len(result.stdout),
                    stderr_length=len(result.stderr),
                )
                if result.stdout:
                    logger.debug("Pytest stdout output", stdout=result.stdout[:1000])
                if result.stderr:
                    logger.warning("Pytest stderr output", stderr=result.stderr[:1000])
                if not os.path.exists(report_path):
                    logger.error(
                        "No report file generated",
                        report_path=report_path,
                        temp_dir_contents=os.listdir(temp_dir),
                    )
                    return (
                        jsonify(
                            {
                                "error": "Test execution failed",
                                "details": "No report generated - possible syntax error",
                                "stdout": result.stdout[:500] if result.stdout else "",
                                "stderr": result.stderr[:500] if result.stderr else "",
                            }
                        ),
                        400,
                    )
                try:
                    with open(report_path) as f:
                        report = json.load(f)
                    log_file_operation("read", report_path, True)
                except Exception as e:
                    logger.error(
                        "Failed to read report file",
                        error=str(e),
                        report_path=report_path,
                    )
                    return jsonify({"error": f"Failed to read report: {str(e)}"}), 500
                logs = []
                passed_tests = 0
                failed_tests = 0
                total_tests = 0
                detailed_failures = []
                for test in report.get("tests", []):
                    total_tests += 1
                    test_name = test.get("nodeid", "Unknown Test")
                    outcome = test.get("outcome", "error")
                    duration = test.get("duration", 0)
                    log_result = ""
                    failure_details = None
                    if outcome == "passed":
                        passed_tests += 1
                        log_result = "Passed"
                    else:
                        failed_tests += 1
                        failure_details = {
                            "test_name": test_name,
                            "outcome": outcome,
                            "duration": duration,
                            "error_message": "",
                            "traceback": "",
                            "stdout": "",
                            "stderr": "",
                        }
                        if outcome == "failed":
                            log_result = "Failed"
                            failure_details["failure_type"] = "Assertion Failure"
                        else:
                            log_result = "Error"
                            failure_details["failure_type"] = "Environment/Setup Error"
                        failure_info = (
                            test.get("call")
                            or test.get("setup")
                            or test.get("teardown")
                        )
                        if failure_info:
                            if "longrepr" in failure_info:
                                failure_details["error_message"] = failure_info[
                                    "longrepr"
                                ]
                            if "stdout" in failure_info:
                                failure_details["stdout"] = failure_info["stdout"]
                            if "stderr" in failure_info:
                                failure_details["stderr"] = failure_info["stderr"]
                            if "traceback" in failure_info:
                                failure_details["traceback"] = failure_info["traceback"]
                        detailed_failures.append(failure_details)
                    logs.append(
                        {
                            "timestamp": datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "action": test_name,
                            "result": log_result,
                            "duration": f"{duration:.2f}s",
                            "details": failure_details,
                        }
                    )
                    log_test_result(test_name, outcome, duration=duration)
                stats = {
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "total": total_tests,
                    "success_rate": (
                        f"{(passed_tests/total_tests*100):.1f}%"
                        if total_tests > 0
                        else "0%"
                    ),
                }
                logger.info(
                    "Test execution results compiled",
                    total_tests=total_tests,
                    passed_tests=passed_tests,
                    failed_tests=failed_tests,
                    logs_count=len(logs),
                    detailed_failures_count=len(detailed_failures),
                )
                total_duration = time.time() - start_time
                log_performance(
                    "run_script",
                    total_duration,
                    total_tests=total_tests,
                    passed_tests=passed_tests,
                    failed_tests=failed_tests,
                )
                return jsonify(
                    {
                        "logs": logs,
                        "stats": stats,
                        "detailed_failures": detailed_failures,
                        "execution_summary": {
                            "total_duration": f"{total_duration:.2f}s",
                            "pytest_return_code": result.returncode,
                            "stdout_preview": (
                                result.stdout[:500] if result.stdout else ""
                            ),
                            "stderr_preview": (
                                result.stderr[:500] if result.stderr else ""
                            ),
                        },
                    }
                )
            except Exception as e:
                logger.error(
                    "Test execution failed", error=str(e), error_type=type(e).__name__
                )
                return (
                    jsonify({"error": "Test execution failed", "details": str(e)}),
                    500,
                )
    except Exception as e:
        logger.error(
            "Unexpected error in run_script", error=str(e), error_type=type(e).__name__
        )
        return jsonify({"error": "Script execution failed", "details": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    logger.info("Health check requested")
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "version": "1.0.0",
        }
    )


@app.route("/logs", methods=["GET"])
def get_logs():
    """Get current log file path for debugging."""
    log_file_path = logger.get_log_file_path()
    return jsonify(
        {
            "log_file_path": log_file_path,
            "log_level": logger.log_level,
            "timestamp": datetime.datetime.now().isoformat(),
        }
    )


@app.route("/view_logs", methods=["GET"])
def view_logs():
    """View current log file contents for debugging."""
    try:
        log_file_path = logger.get_log_file_path()
        if os.path.exists(log_file_path):
            with open(log_file_path, "r") as f:
                log_contents = f.read()
            return jsonify(
                {
                    "log_file_path": log_file_path,
                    "log_contents": log_contents,
                    "file_size": len(log_contents),
                    "last_modified": datetime.datetime.fromtimestamp(
                        os.path.getmtime(log_file_path)
                    ).isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {"error": "Log file not found", "log_file_path": log_file_path}
                ),
                404,
            )
    except Exception as e:
        logger.error("Error reading log file", error=str(e))
        return jsonify({"error": f"Failed to read logs: {str(e)}"}), 500


@app.route("/logs/path:<filename>", methods=["GET"])
def get_specific_log(filename):
    """Get a specific log file from the logs directory."""
    try:
        logs_dir = "./logs"
        log_file_path = os.path.join(logs_dir, filename)
        # Security check - ensure file is within logs directory
        if not os.path.abspath(log_file_path).startswith(os.path.abspath(logs_dir)):
            return jsonify({"error": "Access denied"}), 403
        if os.path.exists(log_file_path):
            with open(log_file_path, "r") as f:
                log_contents = f.read()
            return jsonify(
                {
                    "filename": filename,
                    "log_contents": log_contents,
                    "file_size": len(log_contents),
                    "last_modified": datetime.datetime.fromtimestamp(
                        os.path.getmtime(log_file_path)
                    ).isoformat(),
                }
            )
        else:
            return jsonify({"error": "Log file not found", "filename": filename}), 404
    except Exception as e:
        logger.error("Error reading specific log file", error=str(e), filename=filename)
        return jsonify({"error": f"Failed to read log file: {str(e)}"}), 500


@app.route("/list_logs", methods=["GET"])
def list_logs():
    """List all available log files."""
    try:
        logs_dir = "./logs"
        if not os.path.exists(logs_dir):
            return jsonify({"logs": [], "message": "Logs directory does not exist"})
        log_files = []
        for filename in os.listdir(logs_dir):
            if filename.endswith(".log"):
                file_path = os.path.join(logs_dir, filename)
                stat = os.stat(file_path)
                log_files.append(
                    {
                        "filename": filename,
                        "size": stat.st_size,
                        "last_modified": datetime.datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                        "created": datetime.datetime.fromtimestamp(
                            stat.st_ctime
                        ).isoformat(),
                    }
                )
        log_files.sort(key=lambda x: x["last_modified"], reverse=True)
        return jsonify({"logs": log_files, "total_files": len(log_files)})
    except Exception as e:
        logger.error("Error listing log files", error=str(e))
        return jsonify({"error": f"Failed to list logs: {str(e)}"}), 500


if __name__ == "__main__":
    logger.info(
        "Starting Flask development server", host="localhost", port=5000, debug=True
    )
    app.run(debug=True, port=5000)
