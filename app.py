import streamlit as st
from io import StringIO
import os

st.set_page_config(page_title="AI Automated QA Suite", layout="wide")

st.title("🤖 AI Automated QA Suite")
st.markdown("Automate your website QA with AI-generated Playwright scripts from your recorded interactions.")

with st.sidebar:
    st.header("🛠️ Workflow")
    st.markdown("""
    1. 🏁 **Enter Website URL**
    2. 📄 **Upload Recorded JS File**
    3. 🧠 **Generate Test Cases**
    4. 📝 **Edit & Save Script**
    5. ▶️ **Run Test Cases**
    6. 📥 **Download Results**
    """)
    st.info("Follow the steps to generate and run your automated QA tests.")

# Placeholder functions for backend logic
def generate_playwright_script(js_file_content, functionality):
    # Placeholder: Replace with actual backend/LLM call
    return f"""# Playwright Python script for {functionality}\n# (Generated from JS file)\n\nimport pytest\nfrom playwright.sync_api import sync_playwright\n\ndef test_{functionality.lower()}():\n    pass  # ... generated steps here ...\n"""

def run_playwright_script(script_content):
    # Placeholder: Replace with actual backend execution
    return [
        {"step": "Login page loaded", "result": "Pass"},
        {"step": "Entered credentials", "result": "Pass"},
        {"step": "Clicked Sign In", "result": "Fail"},
    ]

# Stepper/progress bar
steps = ["Enter URL", "Upload JS", "Generate Test Cases", "Edit & Save Script", "Run Tests", "Download"]
current_step = 0

# Step 1: URL input
website_url = st.text_input("🏁 Website URL", placeholder="https://www.example.com")
if website_url:
    current_step = 1

# Step 2: JS file upload
js_file = None
js_file_content = None
if current_step >= 1:
    js_file = st.file_uploader("📄 Upload Playwright JS file", type=["js"])
    if js_file:
        current_step = 2
        st.success(f"Uploaded: {js_file.name}")
        # js_file.seek(0)
        # js_file_content = js_file.read().decode(errors="ignore")
        # with st.expander("Preview JS File", expanded=False):
        #     st.code(js_file_content[:1000], language="javascript")

# Step 3: Describe Test Case Functionality
functionality = ""
generated_script = ""
if current_step >= 2:
    st.markdown("---")
    st.subheader("🧠 Describe the Functionality to Test")
    functionality = st.text_input("What functionality do you want test cases for? (e.g., Login, Signup)")
    if st.button("🚀 Generate Script"):
        # Placeholder for backend call
        generated_script = generate_playwright_script(js_file_content, functionality)
        st.session_state["generated_script"] = generated_script
        st.success("Script generated!")
    if st.session_state.get("generated_script"):
        generated_script = st.session_state["generated_script"]
        current_step = 3

# Step 4: Edit & Save Script
if current_step >= 3 and generated_script:
    st.markdown("---")
    st.subheader("📝 Edit & Save Script")
    edited_script = st.text_area("Edit your Playwright Python script below:", value=generated_script, height=300, key="script_editor")
    if st.button("💾 Save Script"):
        st.session_state["final_script"] = edited_script
        st.success("Script saved!")
    script_to_download = st.session_state.get("final_script", edited_script)
    st.download_button("⬇️ Download Python Script", script_to_download, file_name="test_script.py")
    current_step = 4

# Step 5: Run Test Cases
if current_step >= 4:
    st.markdown("---")
    st.subheader("▶️ Run Test Cases & View Logs")
    if st.button("▶️ Run Script (Placeholder)"):
        logs = run_playwright_script(script_to_download)
        st.session_state["logs"] = logs
        st.success("Test run complete! (placeholder)")
    if st.session_state.get("logs"):
        logs = st.session_state["logs"]
        st.table(logs)
        # Prepare CSV
        import csv
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["step", "result"])
        writer.writeheader()
        writer.writerows(logs)
        st.download_button("⬇️ Download Log CSV", output.getvalue(), file_name="test_log.csv")
        current_step = 5

# Visual progress bar/stepper
st.sidebar.markdown("---")
progress = (current_step + 1) / len(steps)
st.sidebar.progress(progress, text=f"Step {current_step+1} of {len(steps)}: {steps[current_step]}")







