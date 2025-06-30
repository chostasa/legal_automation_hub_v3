import streamlit as st
st.set_page_config(page_title="Legal Automation Hub", layout="wide")

# ✅ Correct way to import modules from scripts folder
from scripts.run_foia import run_foia
from scripts.run_demand import run_demand

import pandas as pd
import os
import zipfile
import io
import tempfile
from docx import Document
from datetime import datetime


st.markdown("""
<style>
.stButton > button {
    background-color: #B08B48;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    font-weight: 600;
}
.stTextInput > div > input {
    border: 1px solid #0A1D3B;
}
.stTextArea > div > textarea {
    border: 1px solid #0A1D3B;
}
</style>
""", unsafe_allow_html=True)

# === Simple login ===
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    password = st.text_input("Enter Password", type="password")
    if password == st.secrets["password"]:
        st.session_state.authenticated = True
        st.rerun()
    else:
        st.stop()

# === Branding: Logo inside navy header bar ===
import base64

def load_logo_base64(file_path):
    with open(file_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

logo_base64 = load_logo_base64("sggh_logo.png")

st.markdown(f"""
<div style="background-color: #0A1D3B; padding: 2rem 0; text-align: center;">
    <img src="data:image/png;base64,{logo_base64}" width="360" style="margin-bottom: 1rem;" />
    <h1 style="color: white; font-size: 2.2rem; margin: 0;">Stinar Gould Grieco & Hensley</h1>
</div>
""", unsafe_allow_html=True)

# === Sidebar Navigation ===
with st.sidebar:
    st.markdown("### ⚖️ Legal Automation Hub")
    tool = st.radio("Choose Tool", [
        "📖 Instructions & Support",
        "📄 Batch Doc Generator",
        "📬 FOIA Requests",
        "📂 Demands",
        "🚧 Complaint (In Progress)",
        "🚧 Subpoenas (In Progress)",
    ])

# === FOIA Requests ===
if tool == "📬 FOIA Requests":
    st.header("📨 Generate FOIA Letters")

    with st.form("foia_form"):
        client_id = st.text_input("Client ID")
        defendant_name = st.text_input("Defendant Name")
        abbreviation = st.text_input("Defendant Abbreviation (for file name)")
        address_line1 = st.text_input("Defendant Address Line 1")
        address_line2 = st.text_input("Defendant Address Line 2 (City, State, Zip)")
        date_of_incident = st.date_input("Date of Incident")
        location = st.text_input("Location of Incident")
        case_synopsis = st.text_area("Case Synopsis")
        potential_requests = st.text_area("Potential Requests (can be reused from another)")
        explicit_instructions = st.text_area("Explicit Instructions (optional)")
        case_type = st.text_input("Case Type")
        facility = st.text_input("Facility or System")
        defendant_role = st.text_input("Defendant Role")

        submitted = st.form_submit_button("Generate FOIA Letter")

    if submitted:
        try:
            # Build DataFrame from form data
            df = pd.DataFrame([{
                "Client ID": client_id,
                "Defendant Name": defendant_name,
                "Defendant Abbreviation": abbreviation,
                "Defendant Line 1 (address)": address_line1,
                "Defendant Line 2 (City,state, zip)": address_line2,
                "DOI": date_of_incident,
                "location of incident": location,
                "Case Synopsis": case_synopsis,
                "Potential Requests": potential_requests,
                "Explicit instructions": explicit_instructions,
                "Case Type": case_type,
                "Facility or System": facility,
                "Defendant Role": defendant_role
            }])

            output_paths = run_foia(df)
            st.success("✅ FOIA letter generated!")

            for path in output_paths:
                filename = os.path.basename(path)
                with open(path, "rb") as f:
                    st.download_button(f"Download {filename}", f, file_name=filename)

        except Exception as e:
            st.error(f"❌ Error: {e}")

# === Demands ===
elif tool == "📂 Demands":
    st.header("📑 Generate Demand Letters")

    st.subheader("📋 Fill in Demand Letter Info")

    with st.form("demand_form"):
        client_name = st.text_input("Client Name")
        defendant = st.text_input("Defendant")
        incident_date = st.date_input("Incident Date")
        location = st.text_input("Location")
        summary = st.text_area("Summary of Incident")
        damages = st.text_area("Damages")

        submitted = st.form_submit_button("Generate Demand Letter")

    if submitted:
        import pandas as pd
        from datetime import datetime

        df = pd.DataFrame([{
            "Client Name": client_name,
            "Defendant": defendant,
            "IncidentDate": incident_date.strftime("%B %d, %Y"),
            "Location": location,
            "Summary": summary,
            "Damages": damages
        }])

        try:
            output_paths = run_demand(df)
            st.success("✅ Letter generated!")

            for path in output_paths:
                filename = os.path.basename(path)
                with open(path, "rb") as f:
                    st.download_button(
                        label=f"Download {filename}",
                        data=f,
                        file_name=filename
                    )
        except Exception as e:
            st.error(f"❌ Error: {e}")

# === Routing ===
if tool == "📄 Batch Doc Generator":
    st.header("📄 Batch Document Generator")

    TEMPLATE_FOLDER = os.path.join("templates", "batch_docs")
    os.makedirs(TEMPLATE_FOLDER, exist_ok=True)

    try:
        campaign_df = pd.read_csv("campaigns.csv")
        CAMPAIGN_OPTIONS = sorted(campaign_df["Campaign"].dropna().unique())
    except Exception as e:
        CAMPAIGN_OPTIONS = []
        st.error(f"❌ Failed to load campaigns.csv: {e}")

    st.markdown("""
    > **How it works:**  
    > 1. Upload a template with `{placeholders}`  
    > 2. Upload Excel with matching column headers  
    > 3. Enter filename format, generate, and download

    ✅ Validates fields  
    📁 Version-safe template naming  
    🔐 No coding required
    """)

    st.subheader("🧾 Template Manager")
    template_mode = st.radio("Choose an action:", ["Upload New Template", "Select a Saved Template", "Template Options"])

    def process_and_preview(template_path, df, output_name_format):
        st.subheader("🔍 Preview First Row of Excel Data")
        st.dataframe(df.head(1))

        st.markdown("**Columns in Excel:**")
        st.code(", ".join(df.columns))

        preview_filename = output_name_format
        for key, val in df.iloc[0].items():
            preview_filename = preview_filename.replace(f"{{{{{key}}}}}", str(val))
        st.markdown("**📄 Preview Filename for First Row:**")
        st.code(preview_filename)

        left, right = "{{", "}}"
        with tempfile.TemporaryDirectory() as temp_dir:
            word_dir = os.path.join(temp_dir, "Word Documents")
            os.makedirs(word_dir)

            for idx, row in df.iterrows():
                doc = Document(template_path)

                for para in doc.paragraphs:
                    for key, val in row.items():
                        if pd.api.types.is_datetime64_any_dtype([val]) or isinstance(val, pd.Timestamp):
                            val = val.strftime("%-m/%-d/%Y")
                        placeholder = f"{left}{key}{right}"
                        for run in para.runs:
                            if placeholder in run.text:
                                run.text = run.text.replace(placeholder, str(val))

                for table in doc.tables:
                    for cell in table._cells:
                        for para in cell.paragraphs:
                            for run in para.runs:
                                for key, val in row.items():
                                    if pd.api.types.is_datetime64_any_dtype([val]) or isinstance(val, pd.Timestamp):
                                        val = val.strftime("%-m/%-d/%Y")
                                    placeholder = f"{left}{key}{right}"
                                    if placeholder in run.text:
                                        run.text = run.text.replace(placeholder, str(val))

                name_for_file = output_name_format
                for key, val in row.items():
                    if pd.api.types.is_datetime64_any_dtype([val]) or isinstance(val, pd.Timestamp):
                        val = val.strftime("%-m/%-d/%Y")
                    name_for_file = name_for_file.replace(f"{left}{key}{right}", str(val))
                filename = name_for_file + ".docx"

                doc_path = os.path.join(word_dir, filename)
                doc.save(doc_path)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zip_out:
                for file in os.listdir(word_dir):
                    full_path = os.path.join(word_dir, file)
                    arcname = os.path.join("Word Documents", file)
                    zip_out.write(full_path, arcname=arcname)

            st.success("✅ Word documents generated!")
            st.download_button(
                label="📦 Download All (Word Only – PDF not supported on Streamlit Cloud)",
                data=zip_buffer.getvalue(),
                file_name="word_documents.zip",
                mime="application/zip"
            )

    if template_mode == "Upload New Template":
        uploaded_template = st.file_uploader("Upload a .docx Template", type="docx")
        campaign_name = st.selectbox("🏷️ Select Campaign for This Template", CAMPAIGN_OPTIONS)
        doc_type = st.text_input("📄 Enter Document Type (e.g., HIPAA, Notice, Demand)")
        excel_file = st.file_uploader("Upload Excel Data (.xlsx)", type="xlsx", key="excel_upload_new")
        output_name_format = st.text_input("Enter filename format (e.g., HIPAA Notice ({{Client Name}}))")

        if uploaded_template and campaign_name and doc_type:
            if st.button("Save and Generate"):
                campaign_safe = campaign_name.replace(" ", "").replace("/", "-")
                doc_type_safe = doc_type.replace(" ", "")
                base_name = f"TEMPLATE_{doc_type_safe}_{campaign_safe}"
                version = 1
                while os.path.exists(os.path.join(TEMPLATE_FOLDER, f"{base_name}_v{version}.docx")):
                    version += 1
                final_filename = f"{base_name}_v{version}.docx"
                save_path = os.path.join(TEMPLATE_FOLDER, final_filename)

                with open(save_path, "wb") as f:
                    f.write(uploaded_template.read())

                st.success(f"✅ Saved as {final_filename}")
                if excel_file and output_name_format:
                    df = pd.read_excel(excel_file)
                    process_and_preview(save_path, df, output_name_format)

    elif template_mode == "Select a Saved Template":
        st.subheader("📂 Select a Saved Template")
        excluded_templates = {"foia_template.docx", "demand_template.docx"}
        available_templates = [
            f for f in os.listdir(TEMPLATE_FOLDER)
            if f.endswith(".docx") and f not in excluded_templates
        ]

        search_query = st.text_input("🔍 Search templates by keyword or campaign").lower()
        filtered_templates = [f for f in available_templates if search_query in f.lower()]

        if not filtered_templates:
            st.warning("⚠️ No matching templates found.")
            st.stop()

        template_choice = st.selectbox("Choose Template", filtered_templates)
        template_path = os.path.join(TEMPLATE_FOLDER, template_choice)
        excel_file = st.file_uploader("Upload Excel Data (.xlsx)", type="xlsx", key="excel_upload_saved")
        output_name_format = st.text_input("Enter filename format (e.g., HIPAA Notice ({{Client Name}}))")

        if st.button("Generate Documents"):
            if excel_file and output_name_format:
                df = pd.read_excel(excel_file)
                process_and_preview(template_path, df, output_name_format)

    elif template_mode == "Template Options":
        st.subheader("⚙️ Template Options")
        excluded_templates = {"foia_template.docx", "demand_template.docx"}
        available_templates = [
            f for f in os.listdir(TEMPLATE_FOLDER)
            if f.endswith(".docx") and f not in excluded_templates
        ]

        search_query = st.text_input("🔍 Search for template to manage").lower()
        filtered_templates = [f for f in available_templates if search_query in f.lower()]

        if filtered_templates:
            template_choice = st.selectbox("Choose Template to Rename/Delete", filtered_templates)
            template_path = os.path.join(TEMPLATE_FOLDER, template_choice)

            st.subheader("✏️ Rename Template")
            new_template_name = st.text_input("New name (no extension)", value=template_choice.replace(".docx", ""))
            if st.button("Rename Template"):
                new_path = os.path.join(TEMPLATE_FOLDER, new_template_name + ".docx")
                if os.path.exists(new_path):
                    st.warning("⚠️ A file with that name already exists.")
                else:
                    os.rename(template_path, new_path)
                    st.success(f"✅ Renamed to {new_template_name}.docx")
                    st.rerun()

            st.subheader("🗑️ Delete Template")
            confirm_delete = st.checkbox("Yes, delete this template permanently.")
            if st.button("Delete Template") and confirm_delete:
                os.remove(template_path)
                st.success(f"✅ Deleted '{template_choice}'")
                st.rerun()

        else:
            st.warning("⚠️ No templates found matching your search.")

elif tool == "📖 Instructions & Support":
    st.header("📘 Instructions")
    st.markdown("""
    Fill in the applicable fields:

    ### 📂 Demands:
    - Client Name
    - Incident Date
    - Summary
    - Damages

    ### 📨 FOIA:
    - Client ID
    - Case Synopsis
    - Potential Requests
    - Case Type
    - Facility or System
    - Defendant Role

    Click **Generate** to create your letters and download the results.
    """)

    st.subheader("🐞 Report a Bug")
    with st.form("report_form"):
        issue = st.text_area("Describe the issue:")
        submitted = st.form_submit_button("Submit")
        if submitted:
            with open("error_reports.txt", "a", encoding="utf-8") as f:
                f.write(issue + "\n---\n")
            st.success("✅ Issue submitted. Thank you!")

else:
    st.warning("🚧 This section is currently under development.")

st.markdown("""
<hr style="margin-top: 2rem;">
<div style="text-align: center; font-size: 0.85rem; color: gray;">
&copy; 2025 Stinar Gould Grieco & Hensley. All rights reserved.
</div>
""", unsafe_allow_html=True)