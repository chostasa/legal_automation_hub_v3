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
from core.auth import get_tenant_id

# === Cleanup expired files from all sessions ===
clean_temp_dir()

TEMPLATE_DIR = os.path.join("templates", "batch_docs", get_tenant_id())
os.makedirs(TEMPLATE_DIR, exist_ok=True)

def run_ui():
    st.header("📄 Batch Document Generator (Saved Templates + Guided Merge)")

    error_code = "BATCH_GEN_001"
    df = None

    # === Step 1: Load Excel Sheet or Dashboard Session ===
    if "dashboard_df" in st.session_state:
        df = st.session_state.dashboard_df.copy()
        st.success(f"✅ Using filtered data from dashboard: {len(df)} rows")
    else:
        uploaded_excel = st.file_uploader("📊 Upload Excel Sheet (.xlsx)", type=["xlsx"])
        if uploaded_excel:
            try:
                df = pd.read_excel(uploaded_excel)
                if df.empty:
                    st.error("❌ Spreadsheet is empty.")
                    df = None
                else:
                    st.success(f"✅ Loaded {len(df)} rows.")
            except Exception as e:
                logger.error(redact_log(f"[{error_code}] ❌ Failed to load Excel: {e}"))
                st.error("❌ Could not read spreadsheet. Please check formatting.")

    # === Step 2: Confirm Columns and Placeholders ===
    if df is not None:
        st.subheader("🔍 Column Headers (Placeholders)")
        st.dataframe(df.head(1), use_container_width=True)

        st.subheader("📎 Placeholders to Use in Word Template")
        for col in df.columns:
            st.code(f"{{{{{col}}}}}", language="jinja")

        st.info("✏️ Be sure your template includes the correct placeholders before continuing.")

        removable_cols = st.multiselect("🧹 Remove columns before merge:", df.columns.tolist())
        if removable_cols:
            df.drop(columns=removable_cols, inplace=True)
            st.success(f"✅ Removed columns: {', '.join(removable_cols)}")

    # === Step 3: Template Mode Selection ===
    if df is not None:
        st.markdown("---")
        st.subheader("📁 Template Manager")

        template_mode = st.radio("Choose Template Mode:", ["Upload New Template", "Select Saved Template", "Template Options"])
        template_path = None
        filename_pattern = st.text_input("Output Filename Pattern", value="Letter_{{Client Name}}.docx")
        folder_pattern = st.text_input("📁 Folder Name Pattern", value="Petitions for {{Client Name}}")
        docname_pattern = st.text_input("📄 Document Name Pattern", value="{{index}} {{Client Name}}.docx")

        if template_mode == "Upload New Template":
            uploaded_template = st.file_uploader("Upload Word Template (.docx)", type=["docx"])
            if uploaded_template:
                template_path = os.path.join(TEMPLATE_DIR, sanitize_filename(uploaded_template.name))
                with open(template_path, "wb") as f:
                    f.write(uploaded_template.read())
                st.success(f"✅ Uploaded and saved as: {os.path.basename(template_path)}")

                template_paths = [template_path]
                selected_templates = [os.path.basename(template_path)]

        elif template_mode == "Select Saved Template":
            available_templates = sorted([f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".docx")])
            search_term = st.text_input("🔍 Search Templates")
            filtered = [t for t in available_templates if search_term.lower() in t.lower()]
            selected_templates = st.multiselect("📂 Choose Template(s)", filtered)
            template_paths = [os.path.join(TEMPLATE_DIR, t) for t in selected_templates]

        elif template_mode == "Template Options":
            st.subheader("⚙️ Template Options")
            available_templates = sorted([f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".docx")])

            search_term = st.text_input("🔍 Search for template to manage")
            filtered_templates = [f for f in available_templates if search_term.lower() in f.lower()]

            if filtered_templates:
                template_choice = st.selectbox("Choose Template to Rename/Delete", filtered_templates)
                template_path = os.path.join(TEMPLATE_DIR, template_choice)

                st.subheader("✏️ Rename Template")
                new_name = st.text_input("New name (no extension)", value=template_choice.replace(".docx", ""))
                if st.button("Rename Template"):
                    new_path = os.path.join(TEMPLATE_DIR, new_name + ".docx")
                    if os.path.exists(new_path):
                        st.warning("⚠️ A file with that name already exists.")
                    else:
                        os.rename(template_path, new_path)
                        st.success(f"✅ Renamed to {new_name}.docx")
                        st.rerun()

                st.subheader("🗑️ Delete Template")
                confirm_delete = st.checkbox("Yes, delete this template permanently.")
                if st.button("Delete Template") and confirm_delete:
                    os.remove(template_path)
                    st.success(f"✅ Deleted '{template_choice}'")
                    st.rerun()

                if available_templates and st.button("🚩 Delete ALL Templates (Cannot Be Undone)"):
                    for t in available_templates:
                        os.remove(os.path.join(TEMPLATE_DIR, t))
                    st.success("✅ All templates deleted.")
                    st.rerun()

            else:
                st.warning("⚠️ No templates found matching your search.")

        # === Step 4: Generate Documents ===
        if selected_templates and template_mode != "Template Options":
            if st.button("⚙️ Generate Documents"):
                try:
                    temp_dir = get_session_temp_dir()
                    zip_buffer = BytesIO()
                    total_success, total_fail = 0, 0

                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_out:
                        for i, row in df.iterrows():
                            try:
                                # Step 1: Prepare replacement map
                                replacements = {
                                    str(k).strip(): sanitize_text(str(v)) if pd.notnull(v) else ""
                                    for k, v in row.items()
                                }
                                replacements["index"] = str(i + 1)

                                # Step 2: Format subfolder for this record
                                folder_name = folder_pattern
                                for key, val in replacements.items():
                                    folder_name = folder_name.replace(f"{{{{{key}}}}}", val.strip())
                                folder_name = sanitize_filename(folder_name)

                                for template_path in template_paths:
                                    template_label = os.path.splitext(os.path.basename(template_path))[0]

                                    # Step 3: Format output document name
                                    output_filename = docname_pattern
                                    for key, val in replacements.items():
                                        output_filename = output_filename.replace(f"{{{{{key}}}}}", val.strip())
                                    output_filename = sanitize_filename(output_filename.replace(".docx", "") + ".docx")

                                    # Step 4: Output path
                                    temp_dir = get_session_temp_dir()
                                    output_path = os.path.join(temp_dir, f"{folder_name}_{output_filename}")

                                    replace_text_in_docx_all(
                                        docx_path=template_path,
                                        replacements=replacements,
                                        save_path=output_path
                                    )

                                    # Step 5: Add to ZIP with folder structure
                                    zip_entry_path = os.path.join(folder_name, output_filename)
                                    with open(output_path, "rb") as f:
                                        zip_out.writestr(zip_entry_path, f.read())

                                    total_success += 1

                            except Exception as doc_err:
                                logger.error(redact_log(f"[{error_code}] ❌ Failed on row {i}: {doc_err}"))
                                total_fail += 1

                    if total_success:
                        st.success(f"✅ {total_success} documents generated.")
                        st.download_button(
                            label="⬇️ Download ZIP of Letters",
                            data=stream_bytesio(zip_buffer),
                            file_name="batch_output.zip",
                            mime="application/zip"
                        )
                        st.caption("⚠️ Generated files will be automatically deleted after 1 hour. Please download promptly.")

                    if total_fail:
                        st.warning(f"⚠️ {total_fail} documents failed to generate. See logs for details.")

                except Exception as e:
                    logger.error(redact_log(f"[{error_code}] ❌ Batch generation failed: {e}"))
                    st.error("❌ Unexpected error occurred. Please contact support.")
