import streamlit as st
import pandas as pd
import os
from io import BytesIO
from tempfile import NamedTemporaryFile

from utils.docx_utils import replace_text_in_docx_all
from utils.session_utils import get_session_temp_dir


def run_ui():
    st.header("🧪 Template Tester")

    with st.form("tester_form"):
        uploaded_template = st.file_uploader("Upload Template (.docx)", type=["docx"])
        key_value_input = st.text_area(
            "Key-Value Replacements (YAML or JSON format)",
            placeholder='''
{
  "Client Name": "Jane Roe",
  "IncidentDate": "June 15, 2023",
  "Facility": "Springfield Center"
}
''',
            height=200
        )
        submitted = st.form_submit_button("🔍 Generate Preview")

    if submitted:
        if not uploaded_template or not key_value_input.strip():
            st.error("❌ Please upload a .docx template and provide replacements.")
            return

        try:
            # Parse JSON or YAML input
            try:
                replacements = eval(key_value_input.strip(), {}, {})
                if not isinstance(replacements, dict):
                    raise ValueError("Input must be a dictionary.")
            except Exception as parse_err:
                st.error(f"❌ Failed to parse replacements: {parse_err}")
                return

            # Render document
            temp_dir = get_session_temp_dir()
            output_path = os.path.join(temp_dir, "preview_output.docx")
            replace_text_in_docx_all(uploaded_template, replacements, output_path)

            st.success("✅ Preview generated!")
            with open(output_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download Rendered Preview",
                    data=f.read(),
                    file_name="preview_output.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

        except Exception as e:
            st.error(f"❌ Failed to generate preview: {e}")
