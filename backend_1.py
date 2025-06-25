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
import textwrap
from utils.logger import (
    get_logger,
)
import ast  # Added for syntax validation of generated scripts

# Initialize logger for backend
logger = get_logger("Backend")

load_dotenv()

# Log backend startup
logger.info(
    "Starting QA-Suite Backend with Dynamic Self-Healing Engine",
    python_version=os.sys.version,
    flask_version="2.3.3",
    langchain_version="0.1.53",
)

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-05-20",
    temperature=0.1,  # Lower temperature for more predictable, stable code
    api_key=os.getenv("GOOGLE_API_KEY"),
)

logger.info(
    "LLM initialized",
    model="gemini-2.5-flash-preview-05-20",
    temperature=0.1,
    api_key_configured=bool(os.getenv("GOOGLE_API_KEY")),
)

app = Flask(__name__)

# ---------------------------------------------------------------------------------
# Configurable constants (can be overridden via environment variables)
# ---------------------------------------------------------------------------------
# Max number of test titles sent to the LLM in a single "slicer" request.
BATCH_SIZE = int(os.getenv("SLICER_BATCH_SIZE", 4))

# ---------------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------------
#   Lightweight Playwright-specific post-processing of LLM output
# ---------------------------------------------------------------------------------


def _fix_expect_page_url(script: str) -> str:
    """Convert JS-style `expect(page.url).to_contain('foo')` to
    Python-Playwright `expect(page).to_have_url(re.compile('foo'))`.
    The replacement is intentionally naive but safe: it preserves the quoted
    URL fragment and pre-pends `.*` so a plain substring match still works.
    """

    def _repl(match: re.Match) -> str:
        url_fragment = match.group(1)
        # keep original quotes – they are part of group(1)
        return f"expect(page).to_have_url(re.compile({url_fragment}))"

    pattern = r"expect\(page\.url\)\.to_contain\(([^)]+)\)"
    return re.sub(pattern, _repl, script)


def _ensure_page_param(script: str) -> str:
    """Guarantee every test function declares a `page` parameter."""

    def _repl(match: re.Match) -> str:
        func_def = match.group(0)
        # group(2) contains the parameter list; group(1) is the function name
        params = match.group(2).strip()
        if not params:
            return func_def.replace("()", "(page)")
        if "page" not in [p.strip() for p in params.split(",")]:
            return func_def.replace("(", "(page, ", 1)
        return func_def  # already fine

    return re.sub(r"def (test_[\w_]+)\(([^)]*)\):", _repl, script)


def sanitize_playwright_script(script: str) -> str:
    """Apply quick, regex-based fixes for common LLM Playwright mistakes.

    The function is intentionally *idempotent* – running it multiple times
    yields the same string.  After sanitisation, syntax validity is checked
    again in the calling context.
    """

    # ------------------------------------------------------------------
    # 1. Remove accidental new-lines inside page.locator(...) calls
    #    Example bad output:  page.locator('button\n', has_text="Sign In")
    #    The fix:           -> page.locator('button', has_text="Sign In")
    # ------------------------------------------------------------------

    def _fix_multiline_locator(match: re.Match) -> str:
        inner = match.group(1)
        # Collapse any CR/LF characters that appear *inside* the parentheses
        # but leave other whitespace intact to preserve readability.
        cleaned = inner.replace("\n", "").replace("\r", "")
        return f"locator({cleaned})"

    script = re.sub(
        r"locator\(([^)]*)\)", _fix_multiline_locator, script, flags=re.DOTALL
    )

    script = _fix_expect_page_url(script)
    script = _ensure_page_param(script)
    return script


# ---------------------------------------------------------------------------------
#   Helper to call the slicer LLM prompt in safe batches
# ---------------------------------------------------------------------------------


def build_sliced_tests_script(js_file_content: str, selected_tests: list[str]) -> str:
    """Generate Playwright tests in batches to stay under the model token limit.

    The first batch retains the imports/fixtures.  Subsequent batches strip all
    leading lines until the first `def test_` so we do not duplicate global
    code.  A blank line is inserted between batches for readability.
    """

    if not selected_tests:
        return ""  # nothing to do

    combined_script_parts: list[str] = []

    for start in range(0, len(selected_tests), BATCH_SIZE):
        batch = selected_tests[start : start + BATCH_SIZE]
        prompt = get_specific_tests_prompt(js_file_content, batch)
        response = llm.invoke(prompt)
        raw_script = clean_llm_output(response.content)

        # For second and later batches remove everything before first test def
        if start != 0:
            split_idx = re.search(r"^def test_", raw_script, re.MULTILINE)
            if split_idx:
                raw_script = raw_script[split_idx.start() :]
        combined_script_parts.append(raw_script.strip())

    return "\n\n".join(combined_script_parts)


def get_specific_tests_prompt(
    js_file_content, selected_tests, website_url="<website_url>", test_ideas=""
):
    selected_tests_json = json.dumps(selected_tests, indent=2)
    return f"""
You are a senior QA automation engineer. Generate a Playwright Python pytest script with the following STRICT requirements. Pay attention to the JS file comments; you may need to use the comments to handle edge cases, and make dedicated pytest functions to ensure a smooth flow of the test cases.

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

7. **Helper Functions (PROHIBITED):**  
    - Each test must be *fully self-contained*.  
    - Do **NOT** create or call helper/utility functions such as `_navigate_to_otp_screen` or `_login_to_otp_page`.  
    - Duplicating setup steps inside every test is acceptable and preferred over sharing helpers.  

8. **Test Naming:**  
     - Name each test function clearly based on the test case description.

9. **Variable Scope (STRICT):**  
    - Do **NOT** introduce undeclared globals (e.g. `WEBSITE_URL`).  
    - Define any constants (like the URL) *inside each test* or as a local variable at the top of the function.  

10. **No Markdown or Explanations:**  
     - Output only the raw Python code, no markdown fences or extra text.

11. **Inputs:**  
    - Website URL: {website_url}
    - JS file actions (for setup and locators):  
      ```javascript
      {js_file_content}
      ```
    - Test cases to generate:  
      {selected_tests_json}
    - User request: {test_ideas}

Follow these rules strictly. Do not invent selectors, URLs, or error messages. Use only what is present in the JS file and the test case descriptions.
"""


@app.route("/generate_test_ideas", methods=["POST"])
def generate_test_ideas():
    start_time = time.time()
    logger.info("Received test ideas generation request")
    try:
        data = request.get_json()
        js_file_content = data.get("js_file_content", "")
        functionality = data.get("functionality", "")

        # ----------------------------------------------------------
        # NEW: Dynamically determine how many ideas the user wants.
        # If the *functionality* string contains a number (e.g. "Generate 5
        # test cases for login"), we honour it.  Otherwise we default to 20 so
        # existing behaviour is preserved.
        # ----------------------------------------------------------
        num_requested = 20  # sensible default
        match = re.search(r"\b(\d+)\b", functionality)
        if match:
            try:
                num_requested = max(1, int(match.group(1)))
                logger.info(
                    "User requested a specific number of test cases.",
                    requested=num_requested,
                )
            except ValueError:
                # Leave num_requested at default and log the parsing issue
                logger.warning(
                    "Could not parse requested number from functionality string – falling back to 20."
                )

        prompt = f"""
You are a QA expert. Based on this Playwright JS file and the '{functionality}' functionality,
generate exactly {num_requested} test case titles in this STRICT JSON format.
JS File:
```javascript
{js_file_content}
```
{{
"test_ideas": [
"Test 1 description",
"Test 2 description",
...
]
}}
Return ONLY the JSON object.
"""
        response = llm.invoke(prompt)
        json_start = response.content.find("{")
        json_end = response.content.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in LLM response")
        json_str = response.content[json_start:json_end]
        test_ideas = json.loads(json_str).get("test_ideas", [])
        result = {"test_ideas": test_ideas[:num_requested]}
        return jsonify(result)
    except Exception as e:
        logger.error("Error in generate_test_ideas", error=str(e), exc_info=True)
        return jsonify({"error": f"Failed to generate test ideas: {str(e)}"}), 500


@app.route("/generate_script", methods=["POST"])
def generate_script():
    start_time = time.time()
    logger.info("Received script generation request")
    try:
        data = request.get_json()
        js_file_content = data.get("js_file_content", "")
        selected_tests = data.get("selected_tests", [])
        # --- Robust generation using batching & sanitisation ---
        script = build_sliced_tests_script(js_file_content, selected_tests)

        script = sanitize_playwright_script(script)

        # Validate LLM output before returning it to the caller
        if not is_valid_python(script):
            return (
                jsonify(
                    {
                        "error": "SyntaxError",
                        "details": "AI-generated script contains invalid Python syntax. Please retry generation.",
                    }
                ),
                500,
            )

        return jsonify({"script": script})
    except Exception as e:
        logger.error("Error in generate_script", error=str(e), exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/generate_full_flow_script", methods=["POST"])
def generate_full_flow_script():
    start_time = time.time()
    logger.info("Received full flow script generation request")
    try:
        data = request.get_json()
        js_file_content = data.get("js_file_content", "")
        task_instructions = (
            "Generate a complete flow test named `test_complete_end_to_end_workflow`."
        )
        prompt = get_specific_tests_prompt(js_file_content, [])
        response = llm.invoke(prompt)
        script = clean_llm_output(response.content)

        # Validate syntax of the full-flow script as well
        if not is_valid_python(script):
            return (
                jsonify(
                    {
                        "error": "SyntaxError",
                        "details": "AI-generated script contains invalid Python syntax. Please retry generation.",
                    }
                ),
                500,
            )

        return jsonify({"script": script})
    except Exception as e:
        logger.error("Error in generate_full_flow_script", error=str(e), exc_info=True)
        return jsonify({"error": str(e)}), 500


# --- SELF-HEALING ENGINE COMPONENTS ---


def get_ai_fix_for_selector(
    failing_command: str, user_intent: str, dom_content: str, error_message: str
):
    """Asks the LLM to provide a fix for a failing Playwright command."""
    logger.info("Attempting AI self-healing for a failing selector.")
    prompt = f"""You are an expert Playwright test automation engineer. A test script has failed with a timeout error. Analyze the situation and provide a more robust selector to fix the script.

Context of Failure:

User's Original Intent (from JS comments):
"{user_intent}"

The Python Command That FAILED:
{failing_command}

The Error Message:
{error_message}

The Full HTML DOM of the page at the moment of failure:
```html
{dom_content}
```

Your Task:
Based on the user's intent and the provided DOM, generate a corrected, more robust Playwright command.

Rules for the New Command:

PRIORITIZE user-facing locators: page.get_by_role(), page.get_by_text(), page.get_by_label(), page.get_by_placeholder(), page.get_by_test_id().

AVOID brittle, style-based selectors like .ant-btn or complex CSS paths.

IF the error message contains "strict mode violation" (multiple elements matched), RETURN a selector guaranteed to match exactly ONE element (e.g., append `.first`, `.nth(0)`, add a `has=` filter, etc.).

The output must be a single line of Python code.

Output Format:
Return ONLY a JSON object in the following format. Do not include any other text or explanations.

{{
  "fixed_command": "page.get_by_role('button', name='Verify').click()"
}}
"""
    try:
        response = llm.invoke(prompt)
        content = response.content
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            return None
        json_str = content[json_start:json_end]
        parsed_response = json.loads(json_str)
        logger.info(
            "AI self-healing provided a potential fix.",
            fix=parsed_response.get("fixed_command"),
        )
        return parsed_response
    except Exception as e:
        logger.error(f"An exception occurred during AI self-healing: {e}")
        return None


def add_dom_dumping_to_script(script_content: str, dom_dump_path: str):
    """Injects a try/except wrapper into every `test_*` function so the DOM is
    automatically dumped when an exception is raised.  Works with *multiple*
    test functions and preserves original indentation, preventing the
    `IndentationError` that occurred previously.

    Args:
        script_content: The raw python test script.
        dom_dump_path: Where to save the DOM when a test fails.
    Returns:
        The augmented script content.
    """

    logger.info("Enhancing test script with automatic DOM dumping on failure.")

    # Collect every test function definition – we need indices to perform string surgery
    test_func_matches = list(re.finditer(r"def (test_\w+)\(page\):", script_content))
    if not test_func_matches:
        return script_content  # Nothing to enhance

    escaped_dom_path = dom_dump_path.replace("\\", "\\\\")

    # Work *backwards* through the script so index calculations remain valid
    for func_match in reversed(test_func_matches):
        func_name = func_match.group(1)
        header_end = func_match.end()  # position right after "):" of def line

        # Determine the indentation used inside this function (first indented line)
        indent_match = re.search(r"\n(\s+)", script_content[header_end:])
        if not indent_match:
            # No indented body – skip (one-liner or malformed)
            continue
        base_indent = indent_match.group(1)

        body_start_idx = header_end + indent_match.end()  # start of first statement

        # Find where this function body ends by scanning until indentation falls back
        remainder = script_content[body_start_idx:]
        lines = remainder.split("\n")
        cumulative_len = 0
        body_end_offset = len(remainder)  # default to end of file
        for i, line in enumerate(lines[1:], 1):  # skip first line, already inside body
            if line.strip() == "":
                cumulative_len += len(line) + 1
                continue
            if not line.startswith(base_indent):
                body_end_offset = cumulative_len
                break
            cumulative_len += len(line) + 1

        original_body = remainder[:body_end_offset]

        # Re-indent body 1 extra level under try block
        indented_body = textwrap.indent(original_body.rstrip("\n"), "    ")

        wrapper = (
            f"\n{base_indent}try:\n"
            f"{indented_body}\n"
            f"{base_indent}except Exception as e:\n"
            f'{base_indent}    print(f"ERROR in {func_name}: Dumping DOM for analysis.")\n'
            f"{base_indent}    try:\n"
            f"{base_indent}        with open(r'{escaped_dom_path}', 'w', encoding='utf-8') as f:\n"
            f"{base_indent}            f.write(page.content())\n"
            f'{base_indent}        print(f"DOM content successfully dumped to {escaped_dom_path}")\n'
            f"{base_indent}    except Exception as dump_error:\n"
            f'{base_indent}        print(f"CRITICAL: Failed to dump DOM: {{dump_error}}")\n'
            f"{base_indent}    raise e\n"
        )

        # Replace the original body with the wrapped version
        script_content = (
            script_content[:body_start_idx] + wrapper + remainder[body_end_offset:]
        )

    return script_content


def extract_failing_context(traceback: str, original_script: str):
    """Parses the traceback to find the failing line and its preceding comment."""
    # This regex is more robust for finding the failing line in the test script
    matches = list(
        re.findall(
            r'File ".*test_script.py", line \d+, in .*\n\s*(page..*)',
            traceback,
        )
    )
    # Fallback: look for the pytest short-form "test_script.py:123:" lines
    if not matches:
        matches = list(
            re.findall(
                r"test_script.py:\d+:.*\n\s*(page..*)",
                traceback,
            )
        )
    if not matches:
        logger.error(
            "Could not parse failing command from traceback.",
            traceback_preview=traceback[-1000:],
        )
        return None, "No specific user intent comment found."
    # The last match in the list is the one that directly caused the error
    failing_command = matches[-1].strip()
    script_lines = original_script.split("\n")
    user_intent = "Perform the action: " + failing_command
    for i, line in enumerate(script_lines):
        if line.strip() == failing_command:
            # Look backwards for the first comment
            for j in range(i - 1, -1, -1):
                if script_lines[j].strip().startswith("#"):
                    user_intent = script_lines[j].strip().lstrip("# ").strip()
                    break
            break
    logger.info(
        "Extracted context for self-healing.",
        failing_command=failing_command,
        user_intent=user_intent,
    )
    return failing_command, user_intent


@app.route("/run_script", methods=["POST"])
def run_script():
    start_time = time.time()
    logger.info("Received script execution request")
    try:
        data = request.get_json()
        script_content = data.get("script_content", "")
        execution_mode = data.get("execution_mode", "specific_tests")

        # If we are *not* in full_flow mode, run once without healing
        if execution_mode != "full_flow":
            logger.info("Running script in STANDARD mode (strict, no self-healing).")
            standard_result = run_standard_test(script_content)
            return jsonify(standard_result)

        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "test_script.py")
            report_path = os.path.join(temp_dir, "report.json")
            dom_dump_path = os.path.join(temp_dir, "dom_on_failure.html")
            healing_attempts = []  # Only populated for self-healing/full-flow mode

            # --- Retry strategy: manual attempts first, followed by AI-healing retries ---
            try:
                manual_retries = int(data.get("manual_retries", 1))
            except (TypeError, ValueError):
                manual_retries = 1

            try:
                max_healing_retries = int(data.get("max_healing_retries", 2))
            except (TypeError, ValueError):
                max_healing_retries = 2

            manual_wait = float(data.get("manual_wait", 10))  # seconds

            total_attempts = 1 + manual_retries + max_healing_retries

            for attempt in range(total_attempts):
                logger.info(
                    f"Starting execution attempt {attempt + 1}/{total_attempts}"
                )
                enhanced_script = add_dom_dumping_to_script(
                    script_content, dom_dump_path
                )
                with open(script_path, "w") as f:
                    f.write(enhanced_script)
                # Use verbose mode (-v) so pytest prints a line per test.  This allows our
                # fallback log parser (when the json-report plugin fails to create a
                # report file) to reliably extract per-test outcomes.
                cmd = [
                    "pytest",
                    "-v",
                    script_path,
                    f"--json-report-file={report_path}",
                    "--capture=no",
                ]
                result = subprocess.run(
                    cmd, cwd=temp_dir, capture_output=True, text=True
                )
                if result.returncode == 0:
                    logger.info(
                        f"Script executed successfully on attempt {attempt + 1}."
                    )
                    break
                if attempt >= (manual_retries + max_healing_retries):
                    logger.error("Max retries reached. Aborting.")
                    break
                logger.warning(f"Script failed on attempt {attempt + 1}.")
                traceback = result.stdout + result.stderr
                # Manual retry phase: attempt < manual_retries
                if attempt < manual_retries:
                    logger.info(
                        f"This was a manual retry ({attempt + 1}/{manual_retries}). Retrying the same script after {manual_wait}s."
                    )
                    time.sleep(max(manual_wait, 0))
                    continue
                traceback_lower = traceback.lower()
                if (
                    "timeouterror" in traceback_lower
                    or "locator expected to be visible" in traceback_lower
                    or "strict mode violation" in traceback_lower
                    or "strict mode error" in traceback_lower
                    or "attributeerror" in traceback_lower
                    or "nameerror" in traceback_lower
                    or "assertionerror" in traceback_lower
                ):
                    failing_command, user_intent = extract_failing_context(
                        traceback, script_content
                    )
                    if not failing_command:
                        logger.error(
                            "Could not parse failing command from traceback. Aborting self-heal."
                        )
                        break
                    dom_content = ""
                    if os.path.exists(dom_dump_path):
                        with open(dom_dump_path, "r", encoding="utf-8") as f:
                            dom_content = f.read()
                    if not dom_content:
                        logger.error(
                            "DOM dump file not found or empty. Aborting self-heal."
                        )
                        break
                    ai_fix = get_ai_fix_for_selector(
                        failing_command, user_intent, dom_content, traceback
                    )
                    if ai_fix and ai_fix.get("fixed_command"):
                        fixed_command = ai_fix["fixed_command"]
                        logger.info(
                            f"AI suggested fix: Replacing '{failing_command}' with '{fixed_command}'"
                        )
                        healing_attempts.append(
                            {
                                "attempt": attempt + 1,
                                "failing_command": failing_command,
                                "fixed_command": fixed_command,
                                "user_intent": user_intent,
                            }
                        )
                        script_content = script_content.replace(
                            failing_command, fixed_command, 1
                        )
                        continue
                    else:
                        logger.error(
                            "AI self-healing did not provide a valid fix. Aborting."
                        )
                        break
                else:
                    logger.warning(
                        "Failure was not a selector timeout. Aborting self-healing."
                    )
                    break
            # --- Final Reporting ---
            if not os.path.exists(report_path):
                if result.returncode == 0:
                    # -------------------------------------------------------------
                    # NEW: Parse pytest stdout to extract per-test results so we can
                    # still report accurate statistics even when the json-report
                    # plugin is missing.  We look for lines of the form:
                    #   test_script.py::test_name PASSED [ 20% ]
                    # and build a list of logs accordingly.  ANSI colour escape
                    # sequences are stripped prior to regex matching.
                    # -------------------------------------------------------------

                    # Helper – strip ANSI sequences for clean parsing
                    ansi_escape = re.compile(r"\x1b\[[0-9;]*[mK]")
                    stdout_clean = ansi_escape.sub("", result.stdout)

                    per_test_pattern = re.compile(
                        r"^(.*?::[\w\[\]-]+)\s+(PASSED|FAILED|ERROR|SKIPPED|XPASS|XFAIL)",
                        re.MULTILINE,
                    )

                    logs_list = []
                    for match in per_test_pattern.finditer(stdout_clean):
                        nodeid = match.group(1).strip()
                        outcome = match.group(2).capitalize()
                        logs_list.append(
                            {
                                "timestamp": datetime.datetime.now().isoformat(
                                    timespec="seconds"
                                ),
                                "action": nodeid,
                                "result": outcome,
                                "duration": "-",
                            }
                        )

                    if logs_list:
                        total = len(logs_list)
                        passed = len([l for l in logs_list if l["result"] == "Passed"])
                        failed = total - passed

                        summary = {
                            "total": total,
                            "passed": passed,
                            "failed": failed,
                            "errors": 0,
                        }
                        stats_obj = {"total": total, "passed": passed, "failed": failed}
                    else:
                        # Fallback to single-entry dummy summary if parsing failed
                        summary = {
                            "total": 1,
                            "passed": int(result.returncode == 0),
                            "failed": int(result.returncode != 0),
                            "errors": 0,
                        }
                        stats_obj = {
                            "total": summary["total"],
                            "passed": summary["passed"],
                            "failed": summary["failed"],
                        }

                    minimal_report = {"summary": summary}

                    # If we have no logs from parsing, create at least suite-level one
                    if not logs_list:
                        logs_list = [
                            {
                                "timestamp": datetime.datetime.now().isoformat(
                                    timespec="seconds"
                                ),
                                "action": "Test Suite",
                                "result": (
                                    "Passed" if summary["failed"] == 0 else "Failed"
                                ),
                                "duration": "0s",
                            }
                        ]

                    return jsonify(
                        {
                            "report": minimal_report,
                            "healing_attempts": healing_attempts,
                            "logs": logs_list,
                            "stats": stats_obj,
                            "final_stdout": result.stdout,
                            "final_stderr": result.stderr,
                        }
                    )
                # Otherwise return error as before
                return (
                    jsonify(
                        {
                            "error": "Test execution failed",
                            "details": "No report generated.",
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "healing_attempts": healing_attempts,
                        }
                    ),
                    400,
                )
            with open(report_path) as f:
                report = json.load(f)
            return jsonify(
                {
                    "report": report,
                    "healing_attempts": healing_attempts,
                    "final_stdout": result.stdout,
                    "final_stderr": result.stderr,
                }
            )
    except Exception as e:
        logger.error("Unexpected error in run_script", error=str(e), exc_info=True)
        return jsonify({"error": "Script execution failed", "details": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for monitoring."""
    logger.info("Health check requested")
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "version": "3.0.0-healing-engine",
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


# ---------------------------------------------------------------------------
# New utility: quick syntax validation for generated Python scripts
# ---------------------------------------------------------------------------


def is_valid_python(code: str) -> bool:
    """Return True if *code* parses as valid Python, else False.

    The check is intentionally lightweight – we use the built-in *ast* module
    so no external dependencies are introduced.  Detailed error information is
    logged to help diagnose LLM output issues.
    """
    try:
        ast.parse(code)
        return True
    except SyntaxError as e:
        logger.error(
            "Generated script failed basic syntax validation",
            error=str(e),
            lineno=getattr(e, "lineno", None),
            text=getattr(e, "text", "")[:120].strip(),
        )
        return False


# ---------------------------------------------------------------------------
#   Simple runner for STRICT mode (no retries, no healing)
# ---------------------------------------------------------------------------


def run_standard_test(script_content: str):
    """Execute *script_content* once via pytest without any retry/healing.

    Returns a python dict compatible with the self-healing runner so the
    frontend UI can handle the response uniformly.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        script_path = os.path.join(temp_dir, "test_script.py")
        report_path = os.path.join(temp_dir, "report.json")

        # Write the provided script to disk
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        # Run in verbose mode so each test outcome is clearly printed –
        # necessary for the stdout-based fallback parser.
        cmd = [
            "pytest",
            "-v",
            script_path,
            f"--json-report-file={report_path}",
            "--capture=no",
        ]
        result = subprocess.run(cmd, cwd=temp_dir, capture_output=True, text=True)

        # If pytest did not create the report file we fabricate a minimal one so
        # the frontend UI still has stats and logs to work with.
        if not os.path.exists(report_path):
            # -------------------------------------------------------------
            # NEW: Parse pytest stdout to extract per-test results so we can
            # still report accurate statistics even when the json-report
            # plugin is missing.  We look for lines of the form:
            #   test_script.py::test_name PASSED [ 20% ]
            # and build a list of logs accordingly.  ANSI colour escape
            # sequences are stripped prior to regex matching.
            # -------------------------------------------------------------

            # Helper – strip ANSI sequences for clean parsing
            ansi_escape = re.compile(r"\x1b\[[0-9;]*[mK]")
            stdout_clean = ansi_escape.sub("", result.stdout)

            per_test_pattern = re.compile(
                r"^(.*?::[\w\[\]-]+)\s+(PASSED|FAILED|ERROR|SKIPPED|XPASS|XFAIL)",
                re.MULTILINE,
            )

            logs_list = []
            for match in per_test_pattern.finditer(stdout_clean):
                nodeid = match.group(1).strip()
                outcome = match.group(2).capitalize()
                logs_list.append(
                    {
                        "timestamp": datetime.datetime.now().isoformat(
                            timespec="seconds"
                        ),
                        "action": nodeid,
                        "result": outcome,
                        "duration": "-",
                    }
                )

            if logs_list:
                total = len(logs_list)
                passed = len([l for l in logs_list if l["result"] == "Passed"])
                failed = total - passed

                summary = {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "errors": 0,
                }
                stats_obj = {"total": total, "passed": passed, "failed": failed}
            else:
                # Fallback to single-entry dummy summary if parsing failed
                summary = {
                    "total": 1,
                    "passed": int(result.returncode == 0),
                    "failed": int(result.returncode != 0),
                    "errors": 0,
                }
                stats_obj = {
                    "total": summary["total"],
                    "passed": summary["passed"],
                    "failed": summary["failed"],
                }

            minimal_report = {"summary": summary}

            # If we have no logs from parsing, create at least suite-level one
            if not logs_list:
                logs_list = [
                    {
                        "timestamp": datetime.datetime.now().isoformat(
                            timespec="seconds"
                        ),
                        "action": "Test Suite",
                        "result": ("Passed" if summary["failed"] == 0 else "Failed"),
                        "duration": "0s",
                    }
                ]

            return {
                "report": minimal_report,
                "healing_attempts": [],
                "logs": logs_list,
                "stats": stats_obj,
                "final_stdout": result.stdout,
                "final_stderr": result.stderr,
            }

        with open(report_path) as f:
            report = json.load(f)

        # -----------------------
        # Build stats & logs back for the UI
        # -----------------------
        summary = report.get("summary", {})
        stats_obj = {
            "total": summary.get("total", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0) + summary.get("errors", 0),
        }

        logs_list = []
        for test in report.get("tests", []):
            logs_list.append(
                {
                    "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                    "action": test.get("nodeid", "test"),
                    "result": test.get("outcome", "unknown").capitalize(),
                    "duration": f"{test.get('duration', 0):.2f}s",
                }
            )

        # Fallback: some pytest-json-report versions omit the per-test list. Extract from stdout.
        if not logs_list:
            # Strip ANSI colour codes for easier parsing
            ansi_escape = re.compile(r"\x1b\[[0-9;]*[mK]")
            stdout_clean = ansi_escape.sub("", result.stdout)

            # Typical line:  test_script.py::test_name PASSED [ 10% ]
            pattern = re.compile(
                r"^(.*?::[\w\[\]-]+)\s+(PASSED|FAILED|ERROR|SKIPPED|XPASS|XFAIL)",
                re.MULTILINE,
            )

            for match in pattern.finditer(stdout_clean):
                nodeid = match.group(1).strip()
                outcome = match.group(2).capitalize()
                logs_list.append(
                    {
                        "timestamp": datetime.datetime.now().isoformat(
                            timespec="seconds"
                        ),
                        "action": nodeid,
                        "result": outcome,
                        "duration": "-",
                    }
                )

            # Update stats based on parsed fallback
            if logs_list:
                stats_obj["total"] = len(logs_list)
                stats_obj["passed"] = len(
                    [l for l in logs_list if l["result"] == "Passed"]
                )
                stats_obj["failed"] = stats_obj["total"] - stats_obj["passed"]

        # If still empty create suite-level entry as last resort
        if not logs_list:
            logs_list.append(
                {
                    "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                    "action": "Test Suite",
                    "result": ("Passed" if summary.get("failed", 0) == 0 else "Failed"),
                    "duration": "0s",
                }
            )

        return {
            "report": report,
            "healing_attempts": [],
            "logs": logs_list,
            "stats": stats_obj,
            "final_stdout": result.stdout,
            "final_stderr": result.stderr,
        }


if __name__ == "__main__":
    logger.info(
        "Starting Flask development server with Dynamic Self-Healing Engine",
        host="localhost",
        port=5000,
        debug=True,
    )
    app.run(debug=True, port=5000)
