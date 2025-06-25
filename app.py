import streamlit as st
import os
import requests
import json
import csv
import io

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

# ---------------------------------------------------------------------------
# Helper functions that call the Flask backend
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def get_test_ideas(js_content: str, functionality: str):
    """Call /generate_test_ideas and return the list."""
    resp = requests.post(
        f"{BACKEND_URL}/generate_test_ideas",
        json={"js_file_content": js_content, "functionality": functionality},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json().get("test_ideas", [])


def generate_playwright_script(js_content: str, selected_tests: list[str]):
    """Generate script via /generate_script (specific tests) or /generate_full_flow_script."""
    if selected_tests:
        endpoint = "/generate_script"
        payload = {"js_file_content": js_content, "selected_tests": selected_tests}
    else:  # fallback to full flow
        endpoint = "/generate_full_flow_script"
        payload = {"js_file_content": js_content}

    resp = requests.post(f"{BACKEND_URL}{endpoint}", json=payload, timeout=300)
    resp.raise_for_status()
    return resp.json()["script"]


def run_playwright_script(script_content: str):
    """Execute the script and return report / logs via /run_script."""
    resp = requests.post(
        f"{BACKEND_URL}/run_script",
        json={"script_content": script_content},
        timeout=900,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="AI Automated QA Suite", layout="wide")

st.title("🤖 AI Automated QA Suite")
st.markdown(
    "Automate your website QA with AI-generated Playwright scripts from your recorded interactions."
)

with st.sidebar:
    st.header("🛠 Workflow")
    st.markdown(
        """
    1. 🏁 **Enter Website URL**
    2. 📄 **Upload Recorded JS File**
    3. 🧠 **Generate & Select Test Ideas**
    4. 📝 **Generate, Edit & Save Script**
    5. ▶️ **Run Test Cases**
    6. 📥 **Download Results**
    """
    )
    st.info("Follow the steps to generate and run your automated QA tests.")


# ---------------------------------------------------------------------------
# Step 1 – Website URL
# ---------------------------------------------------------------------------

if "step" not in st.session_state:
    st.session_state.step = 0

website_url = st.text_input("🏁 Website URL", placeholder="https://www.example.com")
if website_url:
    st.session_state.step = max(st.session_state.step, 1)


# ---------------------------------------------------------------------------
# Step 2 – Upload JS file
# ---------------------------------------------------------------------------

js_content = st.session_state.get("js_content")

if st.session_state.step >= 1:
    js_file = st.file_uploader("📄 Upload Playwright JS file", type=["js"])
    if js_file:
        js_content = js_file.read().decode("utf-8", errors="ignore")
        st.session_state.js_content = js_content
        st.success(f"Uploaded: {js_file.name}")
        st.session_state.step = max(st.session_state.step, 2)
        with st.expander("Preview JS File", expanded=False):
            st.code(js_content[:2000], language="javascript")


# ---------------------------------------------------------------------------
# Step 3 – Generate & select test ideas
# ---------------------------------------------------------------------------

test_ideas = st.session_state.get("test_ideas", [])
selected_tests = st.session_state.get("selected_tests", [])

if st.session_state.step >= 2 and js_content:
    st.markdown("---")
    st.subheader("🧠 Generate Test Ideas")
    functionality = st.text_input(
        "Describe the functionality you want tests for (e.g., Login, Checkout)",
        key="functionality_input",
    )

    if st.button("🔍 Get Test Ideas") and functionality:
        with st.spinner("Calling AI backend – generating ideas..."):
            try:
                test_ideas = get_test_ideas(js_content, functionality)
                st.session_state.test_ideas = test_ideas
                st.success("Received test ideas!")
            except Exception as e:
                st.error(f"Failed to get ideas: {e}")

    if test_ideas:
        selected_tests = st.multiselect(
            "Select the test cases you want to generate:",
            options=test_ideas,
            default=test_ideas[:5],
        )
        st.session_state.selected_tests = selected_tests
        if selected_tests:
            st.session_state.step = max(st.session_state.step, 3)


# ---------------------------------------------------------------------------
# Step 4 – Generate, edit, and save script
# ---------------------------------------------------------------------------

generated_script = st.session_state.get("generated_script")

if st.session_state.step >= 3 and js_content:
    st.markdown("---")
    st.subheader("📝 Generate & Edit Script")

    if st.button("🚀 Generate Script"):
        with st.spinner("Generating Playwright script via backend..."):
            try:
                generated_script = generate_playwright_script(
                    js_content, selected_tests
                )
                st.session_state.generated_script = generated_script
                st.success("Script generated!")
            except Exception as e:
                st.error(f"Script generation failed: {e}")

    if generated_script:
        edited_script = st.text_area(
            "Edit your Playwright Python script below:",
            value=generated_script,
            height=400,
            key="script_editor",
        )
        if st.button("💾 Save Script"):
            st.session_state.final_script = edited_script
            st.success("Script saved!")
        st.session_state.step = max(st.session_state.step, 4)


# ---------------------------------------------------------------------------
# Step 5 – Run tests
# ---------------------------------------------------------------------------

if st.session_state.step >= 4 and st.session_state.get("final_script"):
    st.markdown("---")
    st.subheader("▶️ Run Tests & View Report")

    if st.button("▶️ Run Script"):
        with st.spinner("Executing tests on backend – please wait..."):
            try:
                result = run_playwright_script(st.session_state.final_script)
                st.session_state.run_result = result
                st.success("Test run complete!")
            except Exception as e:
                st.error(f"Execution failed: {e}")

    if run_result := st.session_state.get("run_result"):
        report = run_result.get("report", {})
        st.json(report)

        # Display healing attempts if any
        healing = run_result.get("healing_attempts", [])
        if healing:
            st.markdown("**Self-healing attempts:**")
            st.table(healing)

        # Allow log download
        stdout = run_result.get("final_stdout", "")
        stderr = run_result.get("final_stderr", "")
        st.download_button("⬇️ Download stdout", stdout, file_name="stdout.log")
        st.download_button("⬇️ Download stderr", stderr, file_name="stderr.log")
        st.session_state.step = max(st.session_state.step, 5)


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------

steps_labels = [
    "Enter URL",
    "Upload JS",
    "Generate Ideas",
    "Generate/Edit Script",
    "Run Tests",
    "Done",
]

st.sidebar.markdown("---")
current = st.session_state.step
st.sidebar.progress(
    (current + 1) / len(steps_labels),
    text=f"Step {current+1} of {len(steps_labels)}: {steps_labels[current]}",
)

st.sidebar.markdown(f"Backend: {BACKEND_URL}")
