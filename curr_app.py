import streamlit as st
from io import StringIO
import os
import requests
import json  # Import json for parsing test ideas
from datetime import datetime
import traceback
import logging

st.set_page_config(page_title="AI Automated QA Suite", layout="wide")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    st.markdown("---")
    st.subheader("💡 Prompting Guide")
    st.markdown(
        """
    • **Test a single functionality** – type its name (e.g., `Login`, `Search`, `Checkout`).\n 
    • **Test the *whole* web-flow** – enter **`whole flow`** or leave the functionality blank. You will receive incremental test ideas for every section (e.g., *Login only*, *Login → Form-1*, etc.)\n.
    • **Run the recorded JS exactly once** – enter **`verbatim flow`** / **`sanity`** / **`convert`** to get a single pytest that mirrors the JS events step-by-step.
    """
    )

    # Add error statistics to sidebar
    if st.session_state.get("error_logs") or st.session_state.get("frontend_errors"):
        st.markdown("---")
        st.subheader("🚨 Error Statistics")

        total_errors = len(st.session_state.get("error_logs", [])) + len(
            st.session_state.get("frontend_errors", [])
        )
        test_failures = len(st.session_state.get("error_logs", []))
        system_errors = len(st.session_state.get("frontend_errors", []))

        st.metric("Total Errors", total_errors)
        st.metric("Test Failures", test_failures, delta=f"{test_failures} ❌")
        st.metric("System Errors", system_errors, delta=f"{system_errors} ⚠️")

        if total_errors > 0:
            st.warning(
                f"⚠️ {total_errors} errors detected. Check the Error Logs section below for details."
            )

            # Quick error summary
            if test_failures > 0:
                st.markdown("**Recent Test Failures:**")
                for error in st.session_state.get("error_logs", [])[-3:]:  # Show last 3
                    st.markdown(f"• {error['test_name'][:30]}...")

            if system_errors > 0:
                st.markdown("**Recent System Errors:**")
                for error in st.session_state.get("frontend_errors", [])[
                    -3:
                ]:  # Show last 3
                    st.markdown(f"• {error['type']}: {error['message'][:30]}...")

# Backend endpoints
BACKEND_URL = "http://localhost:5000"

# Initialize session state for error logging
if "error_logs" not in st.session_state:
    st.session_state.error_logs = []
if "frontend_errors" not in st.session_state:
    st.session_state.frontend_errors = []


def log_frontend_error(error_type, error_message, details=None, timestamp=None):
    """Log frontend errors for display"""
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    error_entry = {
        "timestamp": timestamp,
        "type": error_type,
        "message": error_message,
        "details": details or "",
        "stack_trace": traceback.format_exc() if details else "",
    }

    st.session_state.frontend_errors.append(error_entry)
    logger.error(f"Frontend Error [{error_type}]: {error_message}")


def log_test_failure(test_name, error_message, stack_trace=None, additional_info=None):
    """Log test failures with detailed information"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    failure_entry = {
        "timestamp": timestamp,
        "test_name": test_name,
        "error_message": error_message,
        "stack_trace": stack_trace or "",
        "additional_info": additional_info or {},
        "severity": "high" if "timeout" in error_message.lower() else "medium",
    }

    st.session_state.error_logs.append(failure_entry)
    logger.error(f"Test Failure [{test_name}]: {error_message}")


def generate_test_ideas(js_file_content, functionality):
    try:
        response = requests.post(
            f"{BACKEND_URL}/generate_test_ideas",
            json={"js_file_content": js_file_content, "functionality": functionality},
            timeout=30,
        )
        if response.status_code == 200:
            return response.json().get("test_ideas", [])
        else:
            error_msg = f"Backend error (HTTP {response.status_code}): {response.text}"
            log_frontend_error(
                "API_ERROR", error_msg, f"Status: {response.status_code}"
            )
            st.error(f"Error generating test ideas: {response.text}")
            return []
    except requests.exceptions.Timeout:
        error_msg = "Request timeout - backend server took too long to respond"
        log_frontend_error("TIMEOUT", error_msg, "generate_test_ideas")
        st.error("Request timeout. Please try again.")
        return []
    except requests.exceptions.ConnectionError:
        error_msg = "Connection error - cannot reach backend server"
        log_frontend_error("CONNECTION_ERROR", error_msg, "generate_test_ideas")
        st.error(
            "Cannot connect to backend server. Please ensure the server is running."
        )
        return []
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        log_frontend_error("UNEXPECTED_ERROR", error_msg, traceback.format_exc())
        st.error(f"Error generating test ideas: {str(e)}")
        return []


def generate_playwright_script(js_file_content, selected_tests, website_url):
    try:
        response = requests.post(
            f"{BACKEND_URL}/generate_script",
            json={
                "js_file_content": js_file_content,
                "selected_tests": selected_tests,
                "website_url": website_url,
            },
            timeout=60,
        )
        if response.status_code == 200:
            return response.json().get("script", "")
        else:
            error_msg = f"Backend error (HTTP {response.status_code}): {response.text}"
            log_frontend_error(
                "API_ERROR", error_msg, f"Status: {response.status_code}"
            )
            st.error(f"Error generating script: {response.text}")
            return "# Error generating script"
    except requests.exceptions.Timeout:
        error_msg = "Request timeout - script generation took too long"
        log_frontend_error("TIMEOUT", error_msg, "generate_playwright_script")
        st.error("Script generation timeout. Please try again.")
        return "# Error: Script generation timeout"
    except requests.exceptions.ConnectionError:
        error_msg = "Connection error - cannot reach backend server"
        log_frontend_error("CONNECTION_ERROR", error_msg, "generate_playwright_script")
        st.error(
            "Cannot connect to backend server. Please ensure the server is running."
        )
        return "# Error: Cannot connect to backend server"
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        log_frontend_error("UNEXPECTED_ERROR", error_msg, traceback.format_exc())
        st.error(f"Error generating script: {str(e)}")
        return "# Error generating script"


def run_playwright_script(script_content):
    try:
        response = requests.post(
            f"{BACKEND_URL}/run_script",
            json={"script_content": script_content},
            timeout=300,  # 5 minutes timeout for test execution
        )
        if response.status_code == 200:
            return response.json()  # Return the whole dict!
        else:
            error_msg = f"Backend error (HTTP {response.status_code}): {response.text}"
            log_frontend_error(
                "API_ERROR", error_msg, f"Status: {response.status_code}"
            )
            st.error(f"Error running script: {response.text}")
            return {
                "logs": [
                    {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "action": "Error",
                        "result": "Failed to run script",
                    }
                ],
                "stats": {"passed": 0, "failed": 0, "total": 0},
                "error": "Failed to run script",
            }
    except requests.exceptions.Timeout:
        error_msg = "Request timeout - test execution took too long"
        log_frontend_error("TIMEOUT", error_msg, "run_playwright_script")
        st.error("Test execution timeout. Please check if tests are running correctly.")
        return {
            "logs": [
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "Timeout",
                    "result": "Failed",
                    "reason": "Test execution timed out",
                }
            ],
            "stats": {"passed": 0, "failed": 0, "total": 0},
            "error": "Test execution timeout",
        }
    except requests.exceptions.ConnectionError:
        error_msg = "Connection error - cannot reach backend server"
        log_frontend_error("CONNECTION_ERROR", error_msg, "run_playwright_script")
        st.error(
            "Cannot connect to backend server. Please ensure the server is running."
        )
        return {
            "logs": [
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "Connection Error",
                    "result": "Failed",
                    "reason": "Cannot connect to backend server",
                }
            ],
            "stats": {"passed": 0, "failed": 0, "total": 0},
            "error": "Cannot connect to backend server",
        }
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        log_frontend_error("UNEXPECTED_ERROR", error_msg, traceback.format_exc())
        st.error(f"Error running script: {str(e)}")
        return {
            "logs": [
                {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "action": "Error",
                    "result": "Failed",
                    "reason": str(e),
                }
            ],
            "stats": {"passed": 0, "failed": 0, "total": 0},
            "error": "Failed to run script",
        }


# Initialize session state variables
if "current_step" not in st.session_state:
    st.session_state.current_step = 0
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
website_url = st.text_input("🏁 Website URL", placeholder="https://www.example.com")
if website_url:
    st.session_state.current_step = max(st.session_state.current_step, 1)

# Step 2: JS file upload
js_file_content = None
if st.session_state.current_step >= 1:
    js_file = st.file_uploader("📄 Upload Playwright JS file", type=["js"])
    if js_file:
        st.session_state.current_step = max(st.session_state.current_step, 2)
        st.success(f"Uploaded: {js_file.name}")
        js_file.seek(0)
        js_file_content = js_file.read().decode(errors="ignore")
        st.session_state.js_file_content = js_file_content
    else:
        # Retain content if file is deselected but was previously uploaded
        js_file_content = st.session_state.get("js_file_content")


# Step 3: Generate Test Case Ideas
if st.session_state.current_step >= 2:
    st.markdown("---")
    st.subheader("🧠 Describe Functionality & Generate Test Ideas")
    functionality = st.text_input(
        "What functionality do you want test cases for? (e.g., Login, Signup)"
    )

    if st.button("💡 Generate Test Case Ideas"):
        with st.spinner("🧠 Calling AI to generate test ideas..."):
            st.session_state.test_ideas = generate_test_ideas(
                js_file_content, functionality
            )
        if st.session_state.test_ideas:
            st.session_state.current_step = max(st.session_state.current_step, 3)

# Step 4: Select Tests & Generate Script
if st.session_state.current_step >= 3 and st.session_state.test_ideas:
    st.markdown("---")
    st.subheader("🧪 Select Tests & Generate Script")
    selected_tests = []
    for idea in st.session_state.test_ideas:
        if st.checkbox(idea, value=True):
            selected_tests.append(idea)

    if st.button("🚀 Generate Script for Selected Tests"):
        with st.spinner("✍️ Writing the Playwright script..."):
            st.session_state.generated_script = generate_playwright_script(
                js_file_content, selected_tests, website_url
            )
        if st.session_state.generated_script:
            st.session_state.current_step = max(st.session_state.current_step, 4)

# Step 5: Edit & Save Script
if st.session_state.current_step >= 4 and st.session_state.generated_script:
    st.markdown("---")
    st.subheader("📝 Edit & Save Script")
    edited_script = st.text_area(
        "Edit your Playwright Python script below:",
        value=st.session_state.generated_script,
        height=400,
        key="script_editor",
    )
    if st.button("💾 Save Script"):
        st.session_state["final_script"] = edited_script
        st.success("Script saved!")
    script_to_run = st.session_state.get("final_script", edited_script)
    st.session_state.current_step = max(st.session_state.current_step, 5)

# Step 6: Run Test Cases
if st.session_state.current_step >= 5:
    st.markdown("---")
    st.subheader("▶️ Run Test Cases & View Logs")
    if st.button("▶️ Run Script"):
        with st.spinner("...Executing tests..."):
            try:
                response = run_playwright_script(script_to_run)

                # Reset session state
                st.session_state["logs"] = []
                st.session_state["stats"] = {"passed": 0, "failed": 0, "total": 0}

                # Handle response
                if isinstance(response, dict):
                    if "error" in response:
                        error_msg = response.get("error", "Unknown error")
                        log_frontend_error(
                            "TEST_EXECUTION_ERROR", error_msg, "Backend returned error"
                        )
                        st.error(f"Error: {error_msg}")
                        if "logs" in response:
                            st.session_state["logs"] = response["logs"]
                    else:
                        st.session_state["logs"] = response.get("logs", [])
                        st.session_state["stats"] = response.get(
                            "stats", {"passed": 0, "failed": 0, "total": 0}
                        )

                        # Process and log failed tests
                        failed_tests = []
                        for log in st.session_state["logs"]:
                            if log.get("result", "").lower() == "failed":
                                test_name = log.get("action", "Unknown Test")
                                error_reason = log.get(
                                    "reason", "No error details provided"
                                )
                                log_test_failure(
                                    test_name=test_name,
                                    error_message=error_reason,
                                    additional_info={
                                        "timestamp": log.get("timestamp", ""),
                                        "test_type": "playwright_test",
                                    },
                                )
                                failed_tests.append(
                                    {
                                        "name": test_name,
                                        "error": error_reason,
                                        "timestamp": log.get("timestamp", ""),
                                    }
                                )

                        # Log summary of failures
                        if failed_tests:
                            log_frontend_error(
                                "TEST_FAILURES_SUMMARY",
                                f"{len(failed_tests)} tests failed",
                                f"Failed tests: {[test['name'] for test in failed_tests]}",
                            )
                else:
                    error_msg = "Unexpected response format from server"
                    log_frontend_error(
                        "RESPONSE_FORMAT_ERROR",
                        error_msg,
                        f"Response type: {type(response)}",
                    )
                    st.error(error_msg)

            except Exception as e:
                error_msg = f"Failed to run tests: {str(e)}"
                log_frontend_error(
                    "EXECUTION_EXCEPTION", error_msg, traceback.format_exc()
                )
                st.error(error_msg)
                st.session_state["logs"] = [
                    {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "action": f"Error: {str(e)}",
                        "result": "Error",
                        "reason": traceback.format_exc(),
                    }
                ]

    # Display results
    if st.session_state.get("logs"):
        # Create a more visually appealing log display
        st.subheader("📊 Test Execution Results")

        # Display summary metrics first
        stats = st.session_state.get("stats", {"passed": 0, "failed": 0, "total": 0})

        # Calculate success rate
        success_rate = (
            (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        )

        # Create columns for metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Tests", stats["total"], help="Total number of tests executed"
            )

        with col2:
            st.metric(
                "Passed",
                stats["passed"],
                delta=f"{stats['passed']} ✅",
                delta_color="normal",
                help="Number of tests that passed successfully",
            )

        with col3:
            st.metric(
                "Failed",
                stats["failed"],
                delta=f"{stats['failed']} ❌",
                delta_color="inverse",
                help="Number of tests that failed",
            )

        with col4:
            st.metric(
                "Success Rate",
                f"{success_rate:.1f}%",
                help="Percentage of tests that passed",
            )

        # Add a progress bar for visual representation
        if stats["total"] > 0:
            progress_value = stats["passed"] / stats["total"]
            st.progress(
                progress_value,
                text=f"Test Progress: {stats['passed']}/{stats['total']} completed",
            )

        st.markdown("---")

        # Display detailed logs with better formatting
        st.subheader("📋 Detailed Test Logs")

        # Add filter options
        filter_col1, filter_col2 = st.columns([2, 1])
        with filter_col1:
            show_passed = st.checkbox(
                "Show Passed Tests", value=True, key="show_passed"
            )
            show_failed = st.checkbox(
                "Show Failed Tests", value=True, key="show_failed"
            )

        with filter_col2:
            sort_order = st.selectbox(
                "Sort by", ["Time", "Status", "Name"], key="sort_logs"
            )

        # Filter and sort logs
        filtered_logs = []
        for log in st.session_state["logs"]:
            result = log.get("result", "").lower()
            if (
                (result == "passed" and show_passed)
                or (result == "failed" and show_failed)
                or (result not in ["passed", "failed"])
            ):
                filtered_logs.append(log)

        # Sort logs
        if sort_order == "Time":
            filtered_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        elif sort_order == "Status":
            filtered_logs.sort(key=lambda x: x.get("result", "").lower())
        elif sort_order == "Name":
            filtered_logs.sort(key=lambda x: x.get("action", ""))

        # Display filtered logs
        for i, log in enumerate(filtered_logs):
            # Create a container for each log entry
            with st.container():
                # Determine status icon and color
                result = log.get("result", "").lower()
                if result == "passed":
                    status_icon = "✅"
                    status_color = "success"
                    bg_color = "#d4edda"
                    border_color = "#c3e6cb"
                elif result == "failed":
                    status_icon = "❌"
                    status_color = "error"
                    bg_color = "#f8d7da"
                    border_color = "#f5c6cb"
                else:
                    status_icon = "⚠️"
                    status_color = "warning"
                    bg_color = "#fff3cd"
                    border_color = "#ffeaa7"

                # Create columns for the log entry
                col1, col2, col3 = st.columns([1, 4, 1])

                with col1:
                    st.markdown(
                        f"<div style='text-align: center; font-size: 24px;'>{status_icon}</div>",
                        unsafe_allow_html=True,
                    )

                with col2:
                    # Test name/action
                    test_name = log.get("action", "Unknown Test")
                    if "::" in test_name:
                        # Format pytest test names nicely
                        parts = test_name.split("::")
                        if len(parts) >= 2:
                            file_name = parts[0].split("/")[-1]  # Get just filename
                            test_func = parts[-1]
                            display_name = f"**{file_name}** → {test_func}"
                        else:
                            display_name = test_name
                    else:
                        display_name = f"**{test_name}**"

                    st.markdown(
                        f"<div style='font-weight: bold; margin-bottom: 4px;'>{display_name}</div>",
                        unsafe_allow_html=True,
                    )

                    # Result and timestamp
                    result_text = log.get("result", "Unknown")
                    timestamp = log.get("timestamp", "")
                    st.markdown(
                        f"<div style='color: #666; font-size: 0.9em;'>Status: {result_text} | {timestamp}</div>",
                        unsafe_allow_html=True,
                    )

                    # Reason/details (if available)
                    reason = log.get("reason", "")
                    if reason and reason != "Test passed successfully.":
                        st.markdown(
                            f"<div style='color: #d63384; font-size: 0.9em; margin-top: 4px; background-color: {bg_color}; padding: 8px; border-radius: 4px; border-left: 4px solid {border_color};'>{reason}</div>",
                            unsafe_allow_html=True,
                        )

                with col3:
                    # Add expandable details button
                    with st.expander("🔍 Details", expanded=False):
                        st.json(log)

                # Add a subtle separator
                st.markdown(
                    "<hr style='margin: 8px 0; opacity: 0.3;'>", unsafe_allow_html=True
                )

        # Show summary at the bottom
        if filtered_logs:
            st.markdown("---")
            st.markdown(
                f"**Showing {len(filtered_logs)} of {len(st.session_state['logs'])} test results**"
            )

        st.session_state.current_step = max(st.session_state.current_step, 6)

    # Display Error Logs Section
    if st.session_state.get("error_logs") or st.session_state.get("frontend_errors"):
        st.markdown("---")
        st.subheader("🚨 Error Logs & Debug Information")

        # Create tabs for different types of errors
        error_tab1, error_tab2 = st.tabs(["🔴 Test Failures", "⚠️ System Errors"])

        with error_tab1:
            if st.session_state.get("error_logs"):
                st.markdown("### Test Failure Details")
                for i, error in enumerate(st.session_state["error_logs"]):
                    with st.expander(
                        f"❌ {error['test_name']} - {error['timestamp']}",
                        expanded=False,
                    ):
                        col1, col2 = st.columns([1, 1])

                        with col1:
                            st.markdown(f"**Test Name:** {error['test_name']}")
                            st.markdown(f"**Timestamp:** {error['timestamp']}")
                            st.markdown(f"**Severity:** {error['severity']}")

                        with col2:
                            st.markdown(f"**Error Message:**")
                            st.error(error["error_message"])

                        if error.get("stack_trace"):
                            st.markdown("**Stack Trace:**")
                            st.code(error["stack_trace"], language="python")

                        if error.get("additional_info"):
                            st.markdown("**Additional Information:**")
                            st.json(error["additional_info"])
            else:
                st.info("No test failures logged.")

        with error_tab2:
            if st.session_state.get("frontend_errors"):
                st.markdown("### System Error Details")
                for i, error in enumerate(st.session_state["frontend_errors"]):
                    with st.expander(
                        f"⚠️ {error['type']} - {error['timestamp']}", expanded=False
                    ):
                        col1, col2 = st.columns([1, 1])

                        with col1:
                            st.markdown(f"**Error Type:** {error['type']}")
                            st.markdown(f"**Timestamp:** {error['timestamp']}")

                        with col2:
                            st.markdown(f"**Error Message:**")
                            st.error(error["message"])

                        if error.get("details"):
                            st.markdown("**Details:**")
                            st.code(error["details"], language="text")

                        if error.get("stack_trace"):
                            st.markdown("**Stack Trace:**")
                            st.code(error["stack_trace"], language="python")
            else:
                st.info("No system errors logged.")

        # Add error summary
        total_errors = len(st.session_state.get("error_logs", [])) + len(
            st.session_state.get("frontend_errors", [])
        )
        if total_errors > 0:
            st.markdown("---")
            st.markdown(f"**Total Errors Logged: {total_errors}**")

            # Add error export functionality
            if st.button("📥 Export Error Logs"):
                error_export = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "test_failures": st.session_state.get("error_logs", []),
                    "system_errors": st.session_state.get("frontend_errors", []),
                    "summary": {
                        "total_errors": total_errors,
                        "test_failures": len(st.session_state.get("error_logs", [])),
                        "system_errors": len(
                            st.session_state.get("frontend_errors", [])
                        ),
                    },
                }

                st.download_button(
                    "⬇️ Download Error Log JSON",
                    json.dumps(error_export, indent=2),
                    file_name=f"error_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                )

# Step 7: Download Buttons
if st.session_state.current_step >= 6:
    st.markdown("---")
    st.subheader("📥 Download Results")
    st.download_button(
        "⬇️ Download Python Script", script_to_run, file_name="test_script.py"
    )
    if st.session_state.get("logs"):
        import csv
        import io

        output = io.StringIO()
        writer = csv.DictWriter(
            output, fieldnames=["timestamp", "action", "result", "reason"]
        )
        writer.writeheader()
        writer.writerows(st.session_state["logs"])
        st.download_button(
            "⬇️ Download Log CSV", output.getvalue(), file_name="test_log.csv"
        )

    # Add error log downloads
    if st.session_state.get("error_logs") or st.session_state.get("frontend_errors"):
        st.markdown("### 📥 Download Error Logs")

        # Download error logs as JSON
        error_export = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "test_failures": st.session_state.get("error_logs", []),
            "system_errors": st.session_state.get("frontend_errors", []),
            "summary": {
                "total_errors": len(st.session_state.get("error_logs", []))
                + len(st.session_state.get("frontend_errors", [])),
                "test_failures": len(st.session_state.get("error_logs", [])),
                "system_errors": len(st.session_state.get("frontend_errors", [])),
            },
        }

        st.download_button(
            "⬇️ Download Error Log JSON",
            json.dumps(error_export, indent=2),
            file_name=f"error_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )

        # Download error logs as CSV
        if st.session_state.get("error_logs"):
            error_csv_output = io.StringIO()
            error_writer = csv.DictWriter(
                error_csv_output,
                fieldnames=[
                    "timestamp",
                    "test_name",
                    "error_message",
                    "severity",
                    "stack_trace",
                ],
            )
            error_writer.writeheader()

            for error in st.session_state["error_logs"]:
                error_writer.writerow(
                    {
                        "timestamp": error.get("timestamp", ""),
                        "test_name": error.get("test_name", ""),
                        "error_message": error.get("error_message", ""),
                        "severity": error.get("severity", ""),
                        "stack_trace": error.get("stack_trace", ""),
                    }
                )

            st.download_button(
                "⬇️ Download Test Failures CSV",
                error_csv_output.getvalue(),
                file_name=f"test_failures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            )

# Visual progress bar/stepper
st.sidebar.markdown("---")
progress_value = (st.session_state.current_step) / (len(steps) - 1)
st.sidebar.progress(
    progress_value,
    text=f"Step {st.session_state.current_step+1}: {steps[st.session_state.current_step]}",
)
