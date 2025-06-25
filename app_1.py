import streamlit as st
from io import StringIO
import os
import requests
import json
from datetime import datetime
import time
from utils.logger import (
    get_logger,
    log_info,
    log_error,
    log_api_call,
    log_performance,
    log_user_action,
    log_step,
)

# Initialize logger for frontend
logger = get_logger("Frontend")

logger.info(
    "Starting QA-Suite Frontend",
    streamlit_version="1.24.0",  # Note: Streamlit version may vary
    python_version=os.sys.version,
)

st.set_page_config(page_title="AI Automated QA Suite", layout="wide")

st.title("🤖 AI Automated QA Suite")
st.markdown(
    "Automate your website QA with AI-generated Playwright scripts from your recorded interactions."
)

with st.sidebar:
    st.header("🛠️ Workflow")
    st.markdown(
        """
    1. 🏁 **Enter Website URL**
    2. 📄 **Upload Recorded JS File**
    3. 🧠 **Generate Test Ideas**
    4. 🧪 **Select Tests & Generate Script**
    5. 📝 **Edit & Save Script**
    6. ▶️ **Run Test Cases**
    7. 📥 **Download Results**
    """
    )
    st.info("Follow the steps to generate and run your automated QA tests.")

# Backend endpoints
BACKEND_URL = "http://localhost:5000"


def generate_test_ideas(js_file_content, functionality):
    start_time = time.time()
    logger.info(
        "Making API call to generate test ideas",
        functionality=functionality,
        js_content_length=len(js_file_content),
    )

    try:
        response = requests.post(
            f"{BACKEND_URL}/generate_test_ideas",
            json={"js_file_content": js_file_content, "functionality": functionality},
        )

        response_time = time.time() - start_time
        log_api_call(
            "/generate_test_ideas",
            "POST",
            response.status_code,
            response_time,
            functionality=functionality,
            js_content_length=len(js_file_content),
        )

        if response.status_code == 200:
            test_ideas = response.json().get("test_ideas", [])
            logger.info(
                "Test ideas generated successfully",
                test_ideas_count=len(test_ideas),
                response_time=response_time,
            )
            return test_ideas
        else:
            logger.error(
                "Failed to generate test ideas",
                status_code=response.status_code,
                response_text=response.text,
            )
            st.error(f"Error generating test ideas: {response.text}")
            return []

    except Exception as e:
        logger.error(
            "Exception during test ideas generation",
            error=str(e),
            error_type=type(e).__name__,
        )
        st.error(f"Error generating test ideas: {str(e)}")
        return []


def generate_playwright_script(js_file_content, selected_tests, website_url):
    start_time = time.time()
    logger.info(
        "Making API call to generate script",
        website_url=website_url,
        selected_tests_count=len(selected_tests),
        js_content_length=len(js_file_content),
    )

    try:
        response = requests.post(
            f"{BACKEND_URL}/generate_script",
            json={
                "js_file_content": js_file_content,
                "selected_tests": selected_tests,
                "website_url": website_url,
            },
        )

        response_time = time.time() - start_time
        log_api_call(
            "/generate_script",
            "POST",
            response.status_code,
            response_time,
            website_url=website_url,
            selected_tests_count=len(selected_tests),
        )

        if response.status_code == 200:
            script = response.json().get("script", "")
            logger.info(
                "Script generated successfully",
                script_length=len(script),
                response_time=response_time,
            )
            return script
        else:
            logger.error(
                "Failed to generate script",
                status_code=response.status_code,
                response_text=response.text,
            )
            st.error(f"Error generating script: {response.text}")
            return "# Error generating script"

    except Exception as e:
        logger.error(
            "Exception during script generation",
            error=str(e),
            error_type=type(e).__name__,
        )
        st.error(f"Error generating script: {str(e)}")
        return "# Error generating script"


def generate_full_flow_script(js_file_content, website_url):
    start_time = time.time()
    logger.info(
        "Making API call to generate a full flow script",
        website_url=website_url,
        js_content_length=len(js_file_content),
    )

    try:
        response = requests.post(
            f"{BACKEND_URL}/generate_full_flow_script",
            json={
                "js_file_content": js_file_content,
                "website_url": website_url,
            },
        )

        response_time = time.time() - start_time
        log_api_call(
            "/generate_full_flow_script",
            "POST",
            response.status_code,
            response_time,
            website_url=website_url,
        )

        if response.status_code == 200:
            script = response.json().get("script", "")
            logger.info(
                "Full flow script generated successfully",
                script_length=len(script),
                response_time=response_time,
            )
            return script
        else:
            logger.error(
                "Failed to generate full flow script",
                status_code=response.status_code,
                response_text=response.text,
            )
            st.error(f"Error generating full flow script: {response.text}")
            return "# Error generating script"

    except Exception as e:
        logger.error(
            "Exception during full flow script generation",
            error=str(e),
            error_type=type(e).__name__,
        )
        st.error(f"Error generating full flow script: {str(e)}")
        return "# Error generating script"


def run_playwright_script(
    script_content: str,
    execution_mode: str,
    manual_retries: int = 1,
    max_healing_retries: int = 2,
    manual_wait: float = 10.0,
):
    """Execute the provided Playwright script via the backend.

    Parameters
    ----------
    script_content : str
        The Python Playwright test script to execute.
    execution_mode : str
        Either ``"full_flow"`` for self-healing runs or ``"specific_tests"`` for strict runs.
    manual_retries : int, optional
        Number of manual retries before invoking the AI self-healing logic (only used in full-flow mode).
    max_healing_retries : int, optional
        Maximum number of AI healing iterations after the manual retries.
    manual_wait : float, optional
        Seconds to wait between manual retries.
    """

    start_time = time.time()
    logger.info(
        "Making API call to run script",
        script_length=len(script_content),
        execution_mode=execution_mode,
    )

    try:
        response = requests.post(
            f"{BACKEND_URL}/run_script",
            json={
                "script_content": script_content,
                "execution_mode": execution_mode,
                "manual_retries": manual_retries,
                "max_healing_retries": max_healing_retries,
                "manual_wait": manual_wait,
            },
        )

        response_time = time.time() - start_time
        log_api_call(
            "/run_script",
            "POST",
            response.status_code,
            response_time,
            script_length=len(script_content),
            execution_mode=execution_mode,
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(
                "Script executed successfully",
                response_time=response_time,
                has_logs="logs" in result,
                logs_count=len(result.get("logs", [])),
            )
            st.session_state["response_data"] = result
            return result
        else:
            logger.error(
                "Failed to run script",
                status_code=response.status_code,
                response_text=response.text,
            )
            st.error(f"Error running script: {response.text}")
            return {
                "logs": [
                    {
                        "timestamp": "",
                        "action": "Error",
                        "result": "Failed to run script",
                    }
                ],
                "stats": {"passed": 0, "failed": 0, "total": 0},
                "error": "Failed to run script",
            }

    except Exception as e:
        logger.error(
            "Exception during script execution",
            error=str(e),
            error_type=type(e).__name__,
        )
        st.error(f"Error running script: {str(e)}")
        return {
            "logs": [
                {"timestamp": "", "action": "Error", "result": "Failed to run script"}
            ],
            "stats": {"passed": 0, "failed": 0, "total": 0},
            "error": "Failed to run script",
        }


# Initialize session state variables
if "current_step" not in st.session_state:
    st.session_state.current_step = 0
    logger.info("Initialized session state", current_step=0)
if "test_ideas" not in st.session_state:
    st.session_state.test_ideas = []
if "generated_script" not in st.session_state:
    st.session_state.generated_script = ""
if "execution_mode" not in st.session_state:
    # default to strict mode until the user explicitly generates a full-flow script
    st.session_state.execution_mode = "specific_tests"

steps = [
    "Enter URL",
    "Upload JS",
    "Generate Ideas",
    "Generate Script",
    "Edit & Save",
    "Run Tests",
    "Download",
]

# Step 1: URL input
logger.debug("Rendering Step 1: URL input")
website_url = st.text_input("🏁 Website URL", placeholder="https://www.example.com")
if website_url:
    if st.session_state.current_step < 1:
        log_user_action("entered_website_url", url=website_url)
        log_step("Enter Website URL", 1, len(steps), url=website_url)
    st.session_state.current_step = max(st.session_state.current_step, 1)

# Step 2: JS file upload
js_file_content = None
if st.session_state.current_step >= 1:
    logger.debug("Rendering Step 2: JS file upload")
    js_file = st.file_uploader("📄 Upload Playwright JS file", type=["js"])
    # NEW: Added a tip for the user
    st.info(
        "💡 **Tip:** For best results, use a recording tool that generates selectors with `data-testid` or other unique attributes."
    )
    if js_file:
        if st.session_state.current_step < 2:
            log_user_action(
                "uploaded_js_file", filename=js_file.name, file_size=js_file.size
            )
            log_step(
                "Upload JS File",
                2,
                len(steps),
                filename=js_file.name,
                file_size=js_file.size,
            )
        st.session_state.current_step = max(st.session_state.current_step, 2)
        st.success(f"Uploaded: {js_file.name}")
        js_file.seek(0)
        js_file_content = js_file.read().decode(errors="ignore")
        st.session_state.js_file_content = js_file_content
        logger.info(
            "JS file uploaded and processed",
            filename=js_file.name,
            file_size=js_file.size,
            content_length=len(js_file_content),
        )
    else:
        # Retain content if file is deselected but was previously uploaded
        js_file_content = st.session_state.get("js_file_content")

# Step 3: Generate Test Case Ideas
if st.session_state.current_step >= 2:
    logger.debug("Rendering Step 3: Generate test ideas")
    st.markdown("---")
    st.subheader("🧠 Describe Functionality & Generate Test Ideas")
    functionality = st.text_input(
        "What functionality do you want test cases for? (e.g., Login, Signup)"
    )

    if st.button("💡 Generate Test Case Ideas"):
        if functionality:
            log_user_action("clicked_generate_test_ideas", functionality=functionality)
            with st.spinner("🧠 Calling AI to generate test ideas..."):
                start_time = time.time()
                st.session_state.test_ideas = generate_test_ideas(
                    js_file_content, functionality
                )
                generation_time = time.time() - start_time
                log_performance(
                    "test_ideas_generation_ui",
                    generation_time,
                    functionality=functionality,
                    test_ideas_count=len(st.session_state.test_ideas),
                )

            if st.session_state.test_ideas:
                if st.session_state.current_step < 3:
                    log_step(
                        "Generate Test Ideas",
                        3,
                        len(steps),
                        functionality=functionality,
                        test_ideas_count=len(st.session_state.test_ideas),
                    )
                st.session_state.current_step = max(st.session_state.current_step, 3)
                logger.info(
                    "Test ideas generated and step advanced",
                    functionality=functionality,
                    test_ideas_count=len(st.session_state.test_ideas),
                )
        else:
            logger.warning(
                "User attempted to generate test ideas without specifying functionality"
            )
            st.warning("Please specify the functionality to test.")

# Step 4: Select Tests & Generate Script
if st.session_state.current_step >= 3 and st.session_state.test_ideas:
    logger.debug("Rendering Step 4: Select tests and generate script")
    st.markdown("---")
    st.subheader("🧪 Select Tests & Generate Script")
    selected_tests = []
    for idea in st.session_state.test_ideas:
        if st.checkbox(idea, value=True):
            selected_tests.append(idea)

    # Place the buttons in columns for a cleaner layout
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🚀 Generate Script for Selected Tests"):
            if selected_tests:
                log_user_action(
                    "clicked_generate_script",
                    selected_tests_count=len(selected_tests),
                    selected_tests=selected_tests,
                )
                with st.spinner("✍️ Writing the Playwright script..."):
                    start_time = time.time()
                    st.session_state.generated_script = generate_playwright_script(
                        js_file_content, selected_tests, website_url
                    )
                    generation_time = time.time() - start_time
                    log_performance(
                        "script_generation_ui",
                        generation_time,
                        selected_tests_count=len(selected_tests),
                        script_length=len(st.session_state.generated_script),
                    )

                if (
                    st.session_state.generated_script
                    and not st.session_state.generated_script.startswith("# Error")
                ):
                    # STRICT mode – disable healing
                    st.session_state.execution_mode = "specific_tests"
                    if st.session_state.current_step < 4:
                        log_step(
                            "Generate Script",
                            4,
                            len(steps),
                            selected_tests_count=len(selected_tests),
                            script_length=len(st.session_state.generated_script),
                        )
                    st.session_state.current_step = max(
                        st.session_state.current_step, 4
                    )
                    logger.info(
                        "Script generated and step advanced",
                        selected_tests_count=len(selected_tests),
                        script_length=len(st.session_state.generated_script),
                    )
            else:
                logger.warning(
                    "User attempted to generate script without selecting any tests"
                )
                st.warning("Please select at least one test case.")

    with col2:
        # ---- THIS IS THE NEW BUTTON ----
        if st.button("🌊 Generate Full Flow Script"):
            log_user_action("clicked_generate_full_flow_script")
            with st.spinner("✍️ Writing the full end-to-end flow script..."):
                start_time = time.time()
                st.session_state.generated_script = generate_full_flow_script(
                    js_file_content, website_url
                )
                generation_time = time.time() - start_time
                log_performance(
                    "full_flow_script_generation_ui",
                    generation_time,
                    script_length=len(st.session_state.generated_script),
                )

            if (
                st.session_state.generated_script
                and not st.session_state.generated_script.startswith("# Error")
            ):
                # FULL FLOW mode – enable self-healing
                st.session_state.execution_mode = "full_flow"
                if st.session_state.current_step < 4:
                    log_step(
                        "Generate Full Flow Script",
                        4,
                        len(steps),
                        script_length=len(st.session_state.generated_script),
                    )
                st.session_state.current_step = max(st.session_state.current_step, 4)
                logger.info(
                    "Full flow script generated and step advanced",
                    script_length=len(st.session_state.generated_script),
                )

# Step 5: Edit & Save Script
if st.session_state.current_step >= 4 and st.session_state.generated_script:
    logger.debug("Rendering Step 5: Edit and save script")
    st.markdown("---")
    st.subheader("📝 Edit & Save Script")
    edited_script = st.text_area(
        "Edit your Playwright Python script below:",
        value=st.session_state.generated_script,
        height=400,
        key="script_editor",
    )
    if st.button("💾 Save Script"):
        log_user_action(
            "saved_script",
            original_length=len(st.session_state.generated_script),
            edited_length=len(edited_script),
        )
        st.session_state["final_script"] = edited_script
        st.success("Script saved!")
        logger.info(
            "Script saved by user",
            original_length=len(st.session_state.generated_script),
            edited_length=len(edited_script),
        )
    script_to_run = st.session_state.get("final_script", edited_script)
    st.session_state.current_step = max(st.session_state.current_step, 5)

# Step 6: Run Test Cases
if st.session_state.current_step >= 5:
    logger.debug("Rendering Step 6: Run test cases")
    st.markdown("---")
    st.subheader("▶️ Run Test Cases & View Logs")
    # Advanced settings for healing engine
    with st.expander("⚙️ Advanced Run Settings"):
        col_adv1, col_adv2 = st.columns(2)
        with col_adv1:
            manual_retries_input = st.number_input(
                "Manual Retries Before AI Healing",
                min_value=0,
                max_value=5,
                value=int(st.session_state.get("manual_retries", 3)),
                help="How many times to rerun the same script on failure before invoking the AI engine.",
            )
        with col_adv2:
            max_heal_input = st.number_input(
                "Max AI Healing Attempts",
                min_value=1,
                max_value=5,
                value=int(st.session_state.get("max_heal_retries", 3)),
                help="Maximum number of AI fix iterations after manual retries are exhausted.",
            )
        st.session_state.manual_retries = manual_retries_input
        st.session_state.max_heal_retries = max_heal_input
        st.session_state.manual_wait = 10.0  # constant for now, could expose

    if st.button("▶️ Run Script"):
        log_user_action("clicked_run_script", script_length=len(script_to_run))
        with st.spinner("...Executing tests..."):
            try:
                start_time = time.time()
                response = run_playwright_script(
                    script_to_run,
                    st.session_state.execution_mode,
                    manual_retries=int(st.session_state.get("manual_retries", 3)),
                    max_healing_retries=int(
                        st.session_state.get("max_heal_retries", 3)
                    ),
                    manual_wait=float(st.session_state.get("manual_wait", 10.0)),
                )
                execution_time = time.time() - start_time
                log_performance(
                    "script_execution_ui",
                    execution_time,
                    script_length=len(script_to_run),
                )

                # Reset session state
                st.session_state["logs"] = []
                st.session_state["stats"] = {"passed": 0, "failed": 0, "total": 0}

                # Handle response
                if isinstance(response, dict):
                    if "error" in response:
                        logger.error(
                            "Script execution returned error",
                            error=response.get("error"),
                            has_logs="logs" in response,
                        )
                        st.error(f"Error: {response.get('error')}")
                        if "logs" in response:
                            st.session_state["logs"] = response["logs"]
                    else:
                        st.session_state["logs"] = response.get("logs", [])
                        st.session_state["stats"] = response.get(
                            "stats", {"passed": 0, "failed": 0, "total": 0}
                        )
                        st.session_state["detailed_failures"] = response.get(
                            "detailed_failures", []
                        )
                        st.session_state["execution_summary"] = response.get(
                            "execution_summary", {}
                        )
                        st.session_state["response_data"] = response
                        logger.info(
                            "Script execution completed successfully",
                            logs_count=len(st.session_state["logs"]),
                            stats=st.session_state["stats"],
                        )
                else:
                    logger.error(
                        "Unexpected response format from server",
                        response_type=type(response),
                    )
                    st.error("Unexpected response format from server")

                if st.session_state.current_step < 6:
                    log_step(
                        "Run Tests",
                        6,
                        len(steps),
                        logs_count=len(st.session_state.get("logs", [])),
                        stats=st.session_state.get("stats", {}),
                    )

            except Exception as e:
                logger.error(
                    "Exception during script execution in UI",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                st.error(f"Failed to run tests: {str(e)}")
                st.session_state["logs"] = [
                    {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "action": f"Error: {str(e)}",
                        "result": "Error",
                    }
                ]

    # Display results
    if st.session_state.get("logs"):
        # Display execution summary if available
        if st.session_state.get("execution_summary"):
            st.subheader("📊 Execution Summary")
            summary = st.session_state["execution_summary"]
            stats = st.session_state.get("stats", {})
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Duration", summary.get("total_duration", "N/A"))
            with col2:
                st.metric("Passed", stats.get("passed", 0))
            with col3:
                st.metric("Failed / Errored", stats.get("failed", 0))
            with col4:
                st.metric("Total Tests", stats.get("total", 0))

        # UPDATED: Display cleaner test results table without the messy details column
        st.subheader("📋 Test Results")
        # Create a cleaner list of logs for display
        display_logs = [
            {
                "Test Case": log.get("action", "Unknown").split("::")[-1],
                "Result": log.get("result", "Unknown"),
                "Duration": log.get("duration", "0s"),
            }
            for log in st.session_state["logs"]
        ]
        st.table(display_logs)

        stats = st.session_state.get("stats", {"passed": 0, "failed": 0, "total": 0})
        st.metric(
            "Test Results",
            f"{stats['passed']}/{stats['total']} Passed",
            delta=f"{stats['failed']} Failed or Errored",
            delta_color="inverse" if stats["failed"] > 0 else "off",
        )

        # ---- NEW: Visualize AI Self-Healing attempts ----
        response_data = st.session_state.get("response_data", {})
        healing_attempts = (
            response_data.get("healing_attempts", [])
            if isinstance(response_data, dict)
            else []
        )
        if healing_attempts:
            st.subheader("🤖 AI Self-Healing Analysis")
            st.info(
                f"The initial script failed, but the AI engine performed {len(healing_attempts)} repair(s) to pass the test."
            )
            for idx, attempt in enumerate(healing_attempts, start=1):
                with st.expander(f"🩹 Healing Attempt #{idx}", expanded=True):
                    st.write(f"**Intent:** `{attempt.get('user_intent','')}`")
                    st.error(
                        f"**Failed Command:** `{attempt.get('failing_command','')}`"
                    )
                    st.success(
                        f"**AI Suggested Fix:** `{attempt.get('fixed_command','')}`"
                    )
            # reconstruct final healed script
            final_script = script_to_run
            for attempt in healing_attempts:
                fc = attempt.get("failing_command")
                fix = attempt.get("fixed_command")
                if fc and fix:
                    final_script = final_script.replace(fc, fix, 1)
            st.subheader("✅ Final Healed Script")
            st.info("This is the script version that passed after all AI repairs.")
            st.code(final_script, language="python")

        # UPDATED: Display detailed failure information with better categorization
        if st.session_state.get("detailed_failures"):
            st.subheader("🔍 Detailed Failure Analysis")

            for i, failure in enumerate(st.session_state["detailed_failures"]):
                failure_type = failure.get("failure_type", "Failure")

                # Use different icons and titles for different failure types
                if failure_type == "Assertion Failure":
                    expander_title = f"❌ {failure['test_name']} - FAILED"
                else:  # Environment/Setup Error
                    expander_title = f"⚠️ {failure['test_name']} - ERROR"

                with st.expander(expander_title):
                    st.markdown(f"**Type:** `{failure_type}`")
                    st.markdown(f"**Duration:** `{failure['duration']:.2f}s`")

                    error_message = failure.get("error_message", "")

                    # Provide a user-friendly explanation for common environment errors
                    if "net::ERR_ABORTED" in error_message:
                        st.warning(
                            "This test encountered a network error (`net::ERR_ABORTED`). This is often a temporary environment issue, not a bug in the application. It can be caused by the browser closing prematurely or a network request being cancelled."
                        )

                    if error_message:
                        st.markdown("**Error Log:**")
                        st.code(error_message, language="text")

                    if failure.get("stdout"):
                        st.markdown("**Standard Output:**")
                        st.code(failure["stdout"], language="text")

                    if failure.get("stderr"):
                        st.markdown("**Standard Error:**")
                        st.code(failure["stderr"], language="text")

        # Display execution logs if available
        if st.session_state.get("execution_summary"):
            summary = st.session_state["execution_summary"]
            if summary.get("stdout_preview") or summary.get("stderr_preview"):
                st.subheader("📝 Raw Execution Logs")

                if summary.get("stdout_preview"):
                    with st.expander("📤 Standard Output (Preview)"):
                        st.code(summary["stdout_preview"], language="text")

                if summary.get("stderr_preview"):
                    with st.expander("📥 Standard Error (Preview)"):
                        st.code(summary["stderr_preview"], language="text")

        st.session_state.current_step = max(st.session_state.current_step, 6)

# Step 7: Download Buttons
if st.session_state.current_step >= 6:
    logger.debug("Rendering Step 7: Download results")
    st.markdown("---")
    st.subheader("📥 Download Results")

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "⬇️ Download Python Script", script_to_run, file_name="test_script.py"
        )
        if st.session_state.get("logs"):
            import csv
            import io

            output = io.StringIO()
            # UPDATED: CSV download now includes the cleaner details
            writer = csv.DictWriter(
                output,
                fieldnames=["timestamp", "action", "result", "duration", "details"],
            )
            writer.writeheader()
            filtered_logs = []
            for log in st.session_state["logs"]:
                filtered_log = {
                    "timestamp": log.get("timestamp", ""),
                    "action": log.get("action", ""),
                    "result": log.get("result", ""),
                    "duration": log.get("duration", ""),
                    "details": (
                        # Convert dict to string for CSV, or leave empty
                        json.dumps(log.get("details"))
                        if log.get("details")
                        else ""
                    ),
                }
                filtered_logs.append(filtered_log)
            writer.writerows(filtered_logs)
            st.download_button(
                "⬇️ Download Log CSV", output.getvalue(), file_name="test_log.csv"
            )

    with col2:
        # Log Viewer Section
        st.markdown("**🔍 Debug & Logs**")

        if st.button("📋 View Current Logs"):
            try:
                response = requests.get(f"{BACKEND_URL}/view_logs")
                if response.status_code == 200:
                    log_data = response.json()
                    st.text_area(
                        "Current Log File Contents",
                        value=log_data.get("log_contents", "No logs available"),
                        height=300,
                        help=f"Log file: {log_data.get('log_file_path', 'Unknown')}",
                    )
                else:
                    st.error(f"Failed to fetch logs: {response.text}")
            except Exception as e:
                st.error(f"Error fetching logs: {str(e)}")

        if st.button("📁 List All Log Files"):
            try:
                response = requests.get(f"{BACKEND_URL}/list_logs")
                if response.status_code == 200:
                    log_files = response.json().get("logs", [])
                    if log_files:
                        st.markdown("**Available Log Files:**")
                        for log_file in log_files:
                            with st.expander(
                                f"📄 {log_file['filename']} ({log_file['size']} bytes)"
                            ):
                                st.write(f"**Size:** {log_file['size']} bytes")
                                st.write(
                                    f"**Last Modified:** {log_file['last_modified']}"
                                )
                                st.write(f"**Created:** {log_file['created']}")

                                if st.button(
                                    f"View {log_file['filename']}",
                                    key=f"view_{log_file['filename']}",
                                ):
                                    try:
                                        log_response = requests.get(
                                            f"{BACKEND_URL}/logs/{log_file['filename']}"
                                        )
                                        if log_response.status_code == 200:
                                            log_content = log_response.json().get(
                                                "log_contents", ""
                                            )
                                            st.text_area(
                                                f"Contents of {log_file['filename']}",
                                                value=log_content,
                                                height=400,
                                            )
                                        else:
                                            st.error(
                                                f"Failed to fetch log file: {log_response.text}"
                                            )
                                    except Exception as e:
                                        st.error(f"Error fetching log file: {str(e)}")
                    else:
                        st.info("No log files found")
                else:
                    st.error(f"Failed to list logs: {response.text}")
            except Exception as e:
                st.error(f"Error listing logs: {str(e)}")

        log_user_action(
            "downloaded_results",
            script_length=len(script_to_run),
            logs_count=len(st.session_state.get("logs", [])),
        )
        log_step(
            "Download Results",
            7,
            len(steps),
            script_length=len(script_to_run),
            logs_count=len(st.session_state.get("logs", [])),
        )

# Visual progress bar/stepper
st.sidebar.markdown("---")
progress_value = (st.session_state.current_step) / (len(steps) - 1)
st.sidebar.progress(
    progress_value,
    text=f"Step {st.session_state.current_step+1}: {steps[st.session_state.current_step]}",
)

# Log session end
if st.session_state.current_step >= len(steps) - 1:
    logger.info(
        "User completed all workflow steps",
        final_step=st.session_state.current_step,
        total_steps=len(steps),
    )
