import streamlit as st
from io import StringIO
import os
import requests
import json # Import json for parsing test ideas
from datetime import datetime

st.set_page_config(page_title="AI Automated QA Suite", layout="wide")

st.title("🤖 AI Automated QA Suite")
st.markdown("Automate your website QA with AI-generated Playwright scripts from your recorded interactions.")

with st.sidebar:
    st.header("🛠️ Workflow")
    st.markdown("""
    1. 🏁 **Enter Website URL**
    2. 📄 **Upload Recorded JS File**
    3. 🧠 **Generate Test Ideas**
    4. 🧪 **Select Tests & Generate Script**
    5. 📝 **Edit & Save Script**
    6. ▶️ **Run Test Cases**
    7. 📥 **Download Results**
    """)
    st.info("Follow the steps to generate and run your automated QA tests.")

    st.markdown("---")
    st.subheader("💡 Prompting Guide")
    st.markdown("""
    • **Test a single functionality** – type its name (e.g., `Login`, `Search`, `Checkout`).\n 
    • **Test the *whole* web-flow** – enter **`whole flow`**, **`complete sanity`**, **`sanity testing`** or leave the functionality blank. You will receive incremental test ideas for every section (e.g., *Login only*, *Login → Form-1*, etc.)\n.
    • **Run the recorded JS exactly once** – enter **`verbatim flow`** / **`sanity`** / **`convert`** to get a single pytest that mirrors the JS events step-by-step.
    """)

    st.markdown("---")
    if st.button("📖 Guidelines & Best Practices"):
        with st.spinner("Fetching guidelines..."):
            try:
                resp = requests.get("http://localhost:5000/guidelines")
                if resp.status_code == 200:
                    st.markdown(resp.text, unsafe_allow_html=True)
                else:
                    st.error("Failed to fetch guidelines.")
            except Exception as e:
                st.error(f"Error fetching guidelines: {e}")

    st.markdown("---")
    st.info("⏱️ All waits/selectors in generated scripts use a reduced timeout (7 seconds) for faster feedback on failures.")

# Backend endpoints
BACKEND_URL = "http://localhost:5000"

def generate_test_ideas(js_file_content, functionality):
    response = requests.post(
        f"{BACKEND_URL}/generate_test_ideas",
        json={"js_file_content": js_file_content, "functionality": functionality}
    )
    if response.status_code == 200:
        return response.json().get("test_ideas", [])
    st.error(f"Error generating test ideas: {response.text}")
    return []

def generate_playwright_script(js_file_content, selected_tests, website_url):
    response = requests.post(
        f"{BACKEND_URL}/generate_script",
        json={
            "js_file_content": js_file_content,
            "selected_tests": selected_tests,
            "website_url": website_url
        }
    )
    if response.status_code == 200:
        return response.json().get("script", "")
    st.error(f"Error generating script: {response.text}")
    return "# Error generating script"

def run_playwright_script(script_content):
    response = requests.post(
        f"{BACKEND_URL}/run_script",
        json={"script_content": script_content}
    )
    if response.status_code == 200:
        return response.json()  # Return the whole dict!
    st.error(f"Error running script: {response.text}")
    return {
        "logs": [{"timestamp": "", "action": "Error", "result": "Failed to run script"}],
        "stats": {"passed": 0, "failed": 0, "total": 0},
        "error": "Failed to run script"
    }

# Initialize session state variables
if "current_step" not in st.session_state:
    st.session_state.current_step = 0
if "test_ideas" not in st.session_state:
    st.session_state.test_ideas = []
if "generated_script" not in st.session_state:
    st.session_state.generated_script = ""

steps = ["Enter URL", "Upload JS", "Generate Ideas", "Generate Script", "Edit & Save", "Run Tests", "Download"]

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
        js_file_content = st.session_state.get('js_file_content')


# Step 3: Generate Test Case Ideas
if st.session_state.current_step >= 2:
    st.markdown("---")
    st.subheader("🧠 Describe Functionality & Generate Test Ideas")
    functionality = st.text_input("What functionality do you want test cases for? (e.g., Login, Signup)")

    if st.button("💡 Generate Test Case Ideas"):
        with st.spinner("🧠 Calling AI to generate test ideas..."):
            st.session_state.test_ideas = generate_test_ideas(js_file_content, functionality)
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
            st.session_state.generated_script = generate_playwright_script(js_file_content, selected_tests, website_url)
        if st.session_state.generated_script:
            st.session_state.current_step = max(st.session_state.current_step, 4)

# Step 5: Edit & Save Script
if st.session_state.current_step >= 4 and st.session_state.generated_script:
    st.markdown("---")
    st.subheader("📝 Edit & Save Script")
    edited_script = st.text_area("Edit your Playwright Python script below:", value=st.session_state.generated_script, height=400, key="script_editor")
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
                        st.error(f"Error: {response.get('error')}")
                        if "logs" in response:
                            st.session_state["logs"] = response["logs"]
                    else:
                        st.session_state["logs"] = response.get("logs", [])
                        st.session_state["stats"] = response.get("stats", {"passed": 0, "failed": 0, "total": 0})
                else:
                    st.error("Unexpected response format from server")

            except Exception as e:
                st.error(f"Failed to run tests: {str(e)}")
                st.session_state["logs"] = [{
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "action": f"Error: {str(e)}",
                    "result": "Error"
                }]

    # Display results
    if st.session_state.get("logs"):
        st.table(st.session_state["logs"])
        stats = st.session_state.get("stats", {"passed": 0, "failed": 0, "total": 0})
        st.metric("Test Results", 
                 f"{stats['passed']}/{stats['total']} Passed", 
                 delta=f"{stats['failed']} Failed",
                 delta_color="inverse")
        
        st.session_state.current_step = max(st.session_state.current_step, 6)

# Step 7: Download Buttons
if st.session_state.current_step >= 6:
    st.markdown("---")
    st.subheader("📥 Download Results")
    st.download_button("⬇️ Download Python Script", script_to_run, file_name="test_script.py")
    if st.session_state.get("logs"):
        import csv
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["timestamp", "action", "result", "reason"])
        writer.writeheader()
        writer.writerows(st.session_state["logs"])
        st.download_button("⬇️ Download Log CSV", output.getvalue(), file_name="test_log.csv")

# Visual progress bar/stepper
st.sidebar.markdown("---")
progress_value = (st.session_state.current_step) / (len(steps) - 1)
st.sidebar.progress(progress_value, text=f"Step {st.session_state.current_step+1}: {steps[st.session_state.current_step]}")








