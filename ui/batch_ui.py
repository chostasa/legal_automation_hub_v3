import streamlit as st
import pandas as pd
import zipfile
import os
from io import BytesIO

from utils.docx_utils import replace_text_in_docx_all
from utils.session_utils import get_session_temp_dir
from utils.file_utils import clean_temp_dir
from core.security import sanitize_text, sanitize_filename, redact_log
from utils.stream_utils import stream_bytesio
from logger import logger

# Cleanup expired temp files on load
clean_temp_dir()

def run_ui():
    st.header("📄 Batch Document Generator (Guided Merge Preview)")

    error_code = "BATCH_GEN_001"
    df = None

    # === Upload Spreadsheet FIRST ===
    uploaded_excel = st.file_uploader("📊 Upload Excel Sheet (.xlsx)", type=["xlsx"])

    if uploaded_excel:
        try:
            df = pd.read_excel(uploaded_excel)
            if df.empty:
                st.error("❌ Spreadsheet is empty.")
                df = None
            else:
                st.success(f"✅ Loaded {len(df)} rows.")
                st.subheader("🔍 Column Headers (Placeholders)")
                st.dataframe(df.head(1), use_container_width=True)

                st.subheader("📎 Placeholders to Use in Word Template")
                st.markdown("Use the following placeholders in your Word document (e.g. `{{Client Name}}`):")
                for col in df.columns:
                    st.code(f"{{{{{col}}}}}", language="jinja")

                st.info("✏️ Open your Word template in Microsoft Word and insert the placeholders above. Then upload it below to generate documents.")

        except Exception as e:
            logger.error(redact_log(f"[{error_code}] ❌ Failed to load Excel: {e}"))
            st.error(f"❌ Could not read spreadsheet (code: {error_code}).")
            df = None

    # === Upload Word Template and Generate ===
    if df is not None:
        st.markdown("---")
        st.subheader("📄 Upload Word Template and Generate")

        uploaded_template = st.file_uploader("Upload Word Template (.docx)", type=["docx"])
        filename_pattern = st.text_input("Output Filename Pattern", value="Letter_{{Client Name}}.docx")
        generate = st.button("⚙️ Generate Documents")

        if generate:
            if not uploaded_template or not uploaded_template.name.endswith(".docx"):
                st.error("❌ Please upload a valid .docx template.")
                return

            try:
                temp_dir = get_session_temp_dir()
                zip_buffer = BytesIO()
                total_success, total_fail = 0, 0

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
                        output_path = os.path.join(temp_dir, f"temp_{i}.docx")

                        try:
                            replace_text_in_docx_all(
                                docx_path=uploaded_template,
                                replacements=replacements,
                                save_path=output_path
                            )

                            with open(output_path, "rb") as f:
                                zip_out.writestr(output_filename, f.read())

                            total_success += 1

                        except Exception as doc_err:
                            logger.error(redact_log(f"[{error_code}] ❌ Failed on row {i}: {doc_err}"))
                            total_fail += 1
                            continue

                if total_success:
                    st.success(f"✅ {total_success} documents generated.")
                    st.download_button(
                        label="⬇️ Download ZIP of Letters",
                        data=stream_bytesio(zip_buffer),
                        file_name="batch_output.zip",
                        mime="application/zip"
                    )

                if total_fail:
                    st.warning(f"⚠️ {total_fail} documents failed. See logs for more info.")

            except Exception as e:
                logger.error(redact_log(f"[{error_code}] ❌ Batch generation failed: {e}"))
                st.error(f"❌ Unexpected error occurred (code: {error_code}). Please contact support.")
