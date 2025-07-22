import streamlit as st
import os
import json
import yaml
from io import BytesIO

from utils.docx_utils import replace_text_in_docx_all
from utils.session_utils import get_session_temp_dir
from utils.file_utils import clean_temp_dir
from core.security import redact_log
from logger import logger

clean_temp_dir()


def parse_input_replacements(input_str: str) -> dict:
    """
    Safely parse JSON or YAML input into a dictionary.
    Raises ValueError if invalid or unsafe.
    """
    try:
        return json.loads(input_str)
    except json.JSONDecodeError:
        try:
            return yaml.safe_load(input_str)
        except yaml.YAMLError as e:
            raise ValueError("Input must be valid JSON or YAML.") from e


def stream_file(path: str):
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk


def run_ui():
    st.header("🧪 Template Tester")

    with st.form("tester_form"):
        uploaded_template = st.file_uploader("Upload Template (.docx)", type=["docx"])
        key_value_input = st.text_area(
            "Key-Value Replacements (YAML or JSON format)",
            placeholder='''{
  "Client Name": "Jane Roe",
  "IncidentDate": "June 15, 2023",
  "Facility": "Springfield Center"
}''',
            height=200
        )
        submitted = st.form_submit_button("🔍 Generate Preview")

    if submitted:
        if not uploaded_template or not key_value_input.strip():
            st.error("❌ Please upload a .docx template and provide replacements.")
            return

        try:
            replacements = parse_input_replacements(key_value_input.strip())
            if not isinstance(replacements, dict):
                raise ValueError("Parsed input must be a dictionary.")

            temp_dir = get_session_temp_dir()
            output_path = os.path.join(temp_dir, "preview_output.docx")

            replace_text_in_docx_all(uploaded_template, replacements, output_path)

            st.success("✅ Preview generated!")
            st.download_button(
                label="⬇️ Download Rendered Preview",
                data=stream_file(output_path),
                file_name="preview_output.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        except Exception as e:
            logger.error(redact_log(f"❌ Template preview generation failed: {e}"))
            st.error("❌ Failed to generate preview. Please check your inputs.")
