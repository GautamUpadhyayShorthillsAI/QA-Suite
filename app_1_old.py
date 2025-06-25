import streamlit as st
from io import StringIO
import os
import requests
import json  # Import json for parsing test ideas
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
    streamlit_version="1.24.0",
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


def run_playwright_script(script_content):
    start_time = time.time()
    logger.info("Making API call to run script", script_length=len(script_content))

    try:
        response = requests.post(
            f"{BACKEND_URL}/run_script", json={"script_content": script_content}
        )

        response_time = time.time() - start_time
        log_api_call(
            "/run_script",
            "POST",
            response.status_code,
            response_time,
            script_length=len(script_content),
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(
                "Script executed successfully",
                response_time=response_time,
                has_logs="logs" in result,
                logs_count=len(result.get("logs", [])),
            )
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
        # Provide guidance on selector robustness
        st.info(
            "Tip: For best results, use a recording tool (or add attributes) that generates *unique* selectors such as `data-testid`, element `id`, or explicit `role` information. Generic utility classes (e.g., `.btn`, `.h-9`) can lead to flaky tests."
        )
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
                if st.session_state.current_step < 4:
                    log_step(
                        "Generate Script",
                        4,
                        len(steps),
                        selected_tests_count=len(selected_tests),
                        script_length=len(st.session_state.generated_script),
                    )
                st.session_state.current_step = max(st.session_state.current_step, 4)
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
    if st.button("▶️ Run Script"):
        log_user_action("clicked_run_script", script_length=len(script_to_run))
        with st.spinner("...Executing tests..."):
            try:
                start_time = time.time()
                response = run_playwright_script(script_to_run)
                execution_time = time.time() - start_time
                log_performance(
                    "script_execution_ui",
                    execution_time,
                    script_length=len(script_to_run),
                )

                # Reset session state
                st.session_state["logs"] = []
                st.session_state["stats"] = {
                    "passed": 0,
                    "failed": 0,
                    "errors": 0,
                    "total": 0,
                }

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
                            "stats", {"passed": 0, "failed": 0, "errors": 0, "total": 0}
                        )
                        st.session_state["detailed_failures"] = response.get(
                            "detailed_failures", []
                        )
                        st.session_state["execution_summary"] = response.get(
                            "execution_summary", {}
                        )
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
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Duration", summary.get("total_duration", "N/A"))
            with col2:
                st.metric("Return Code", summary.get("pytest_return_code", "N/A"))
            with col3:
                st.metric(
                    "Success Rate",
                    st.session_state.get("stats", {}).get("success_rate", "N/A"),
                )
            with col4:
                st.metric(
                    "Total Tests", st.session_state.get("stats", {}).get("total", 0)
                )

        # Display test results table
        st.subheader("📋 Test Results")
        # Simplify table by omitting the verbose `details` column for readability
        logs_to_display = [
            {
                "timestamp": log.get("timestamp", ""),
                "action": log.get("action", ""),
                "result": (
                    "⚠️ Environment Error"
                    if log.get("result") == "Error"
                    else log.get("result")
                ),
                "duration": log.get("duration", ""),
            }
            for log in st.session_state["logs"]
        ]
        st.table(logs_to_display)

        # Extract basic stats (now includes `errors` returned by backend)
        stats_defaults = {"passed": 0, "failed": 0, "errors": 0, "total": 0}
        stats = {**stats_defaults, **st.session_state.get("stats", {})}

        col_pass, col_fail, col_err = st.columns(3)
        with col_pass:
            st.metric("Passed", stats["passed"], help="Total tests that passed")
        with col_fail:
            st.metric("Failed", stats["failed"], help="Assertion failures")
        with col_err:
            st.metric("Errors", stats["errors"], help="Environment/setup errors")

        # Offer to rerun failed/error tests only
        failed_or_error_tests = [
            log["action"]
            for log in st.session_state["logs"]
            if log.get("result") in ("Fail", "⚠️ Environment Error", "Error")
            and log.get("action", "").startswith("test_")
        ]

        if failed_or_error_tests:
            st.markdown("---")
            if st.button("🔄 Rerun Failed/Error Tests"):
                st.info("Regenerating script for failed/error tests…")

                js_content_for_rerun = st.session_state.get("js_file_content", "")
                with st.spinner("Generating new script"):
                    new_script = generate_playwright_script(
                        js_content_for_rerun, failed_or_error_tests, website_url
                    )

                with st.spinner("Executing failed/error tests again"):
                    rerun_result = run_playwright_script(new_script)

                # Update session state with rerun results
                st.session_state["logs"] = rerun_result.get("logs", [])
                st.session_state["stats"] = rerun_result.get("stats", stats_defaults)
                st.session_state["detailed_failures"] = rerun_result.get(
                    "detailed_failures", []
                )
                st.session_state["execution_summary"] = rerun_result.get(
                    "execution_summary", {}
                )

                st.success("Rerun complete – results updated above.")

                # ==== Always-visible Failure Details and Execution Logs ====
                if st.session_state.get("detailed_failures"):
                    st.subheader("🔍 Detailed Failure Analysis")
                    for failure in st.session_state["detailed_failures"]:
                        with st.expander(
                            f"❌ {failure['test_name']} - {failure['outcome'].upper()}"
                        ):
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                st.markdown("**Test Information:**")
                                st.write(f"**Duration:** {failure['duration']:.2f}s")
                                st.write(f"**Outcome:** {failure['outcome']}")

                                if failure.get("error_message"):
                                    st.markdown("**Error Message:**")
                                    st.code(failure["error_message"], language="text")

                            with col2:
                                if failure.get("traceback"):
                                    st.markdown("**Traceback:**")
                                    st.code(failure["traceback"], language="python")

                                if failure.get("stdout"):
                                    st.markdown("**Standard Output:**")
                                    st.code(failure["stdout"], language="text")

                                if failure.get("stderr"):
                                    st.markdown("**Standard Error:**")
                                    st.code(failure["stderr"], language="text")

                if st.session_state.get("execution_summary"):
                    summary = st.session_state["execution_summary"]
                    if summary.get("stdout_preview") or summary.get("stderr_preview"):
                        st.subheader("📝 Execution Logs")
                        if summary.get("stdout_preview"):
                            with st.expander("📤 Standard Output"):
                                st.code(summary["stdout_preview"], language="text")
                        if summary.get("stderr_preview"):
                            with st.expander("📥 Standard Error"):
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
                        str(log.get("details", "")) if log.get("details") else ""
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
            logs_count=len(st.session_state["logs"]),
        )
        log_step(
            "Download Results",
            7,
            len(steps),
            script_length=len(script_to_run),
            logs_count=len(st.session_state["logs"]),
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
