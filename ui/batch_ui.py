import streamlit as st
import pandas as pd
import zipfile
import os
from io import BytesIO
from utils.docx_utils import replace_text_in_docx_all
from utils.session_utils import get_session_temp_dir
from core.security import sanitize_text, sanitize_filename, redact_log
from logger import logger

def run_ui():
    st.header("📄 Batch Document Generator")

    with st.form("batch_form"):
        uploaded_template = st.file_uploader("Upload .docx Template", type=["docx"])
        uploaded_excel = st.file_uploader("Upload .xlsx Spreadsheet", type=["xlsx"])
        filename_pattern = st.text_input("Filename Pattern", value="Letter_{{Client Name}}.docx")

        submitted = st.form_submit_button("Generate All Documents")

    if submitted:
        if not uploaded_template or not uploaded_excel:
            st.error("❌ Please upload both a template and a spreadsheet.")
            return

        try:
            df = pd.read_excel(uploaded_excel)
            if df.empty:
                st.error("❌ Spreadsheet is empty.")
                return

            st.success(f"✅ Loaded {len(df)} rows from spreadsheet.")

            temp_dir = get_session_temp_dir()
            zip_buffer = BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
                for i, row in df.iterrows():
                    replacements = {
                        str(k).strip(): sanitize_text(str(v)) if pd.notnull(v) else ""
                        for k, v in row.items()
                    }

                    output_filename = filename_pattern
                    for key, val in replacements.items():
                        output_filename = output_filename.replace(f"{{{{{key}}}}}", val.strip())

                    output_filename = sanitize_filename(output_filename or f"Letter_{i}.docx")

                    try:
                        output_path = os.path.join(temp_dir, f"temp_{i}.docx")
                        replace_text_in_docx_all(
                            docx_path=uploaded_template,
                            replacements=replacements,
                            save_path=output_path
                        )

                        with open(output_path, "rb") as f:
                            zip_out.writestr(output_filename, f.read())

                    except Exception as doc_err:
                        logger.error(redact_log(f"❌ Failed to generate doc for row {i}: {doc_err}"))
                        continue  # Skip failed row and continue

            st.success("✅ All documents generated!")

            st.download_button(
                label="⬇️ Download ZIP of Letters",
                data=zip_buffer.getvalue(),
                file_name="batch_output.zip",
                mime="application/zip"
            )

        except Exception as e:
            logger.error(redact_log(f"❌ Batch generation failed: {e}"))
            st.error("❌ An error occurred during batch generation.")
