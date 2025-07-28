import streamlit as st
import pandas as pd
import os
import asyncio
from io import BytesIO

from services.style_transfer_service import run_batch_style_transfer
from core.security import mask_phi, redact_log, sanitize_filename
from core.auth import get_tenant_id, get_user_role
from core.audit import log_audit_event
from core.error_handling import handle_error
from core.usage_tracker import check_quota, decrement_quota
from logger import logger


def run_style_transfer_ui():
    st.title("🧠 Style Mimic Generator")
    st.markdown("""
Upload one or more **example paragraphs**, then either upload an Excel file of inputs **or** paste them directly into the app.
Each input will be rewritten to match the **tone, structure, and legal voice** of the example(s).

- Separate multiple example paragraphs with `---`
- Pasted inputs should also be separated with `---`
""")

    tenant_id = get_tenant_id()
    user_role = get_user_role()
    EXAMPLE_DIR = os.path.join("examples", tenant_id, "style_transfer")
    os.makedirs(EXAMPLE_DIR, exist_ok=True)

    st.subheader("🎨 Choose or Add Example Paragraph(s)")

    # Load saved examples
    try:
        available_examples = [f for f in os.listdir(EXAMPLE_DIR) if f.endswith(".txt")]
    except Exception as e:
        msg = handle_error(e, code="STYLE_UI_001")
        st.error(msg)
        return

    selected_example = st.selectbox("📂 Select Existing Example (optional)", ["None"] + available_examples)

    example_text = ""
    if selected_example != "None":
        try:
            with open(os.path.join(EXAMPLE_DIR, selected_example), "r", encoding="utf-8") as f:
                example_text = f.read()
            with st.expander("🧠 Preview Selected Example"):
                st.code(example_text[:3000], language="markdown")
        except Exception as e:
            msg = handle_error(e, code="STYLE_UI_002")
            st.error(msg)

    example_input = st.text_area(
        "✍️ Paste Example Paragraph(s) (separate with '---')",
        height=250,
        value=example_text
    )
    example_list = [p.strip() for p in example_input.split("---") if p.strip()]

    # Save example if admin
    if example_input.strip() and st.button("💾 Save as Example"):
        try:
            if user_role.lower() != "admin":
                st.error("❌ Only Admins can save style examples.")
            else:
                filename = sanitize_filename(f"example_{len(available_examples)+1}.txt")
                path = os.path.join(EXAMPLE_DIR, filename)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(example_input)
                st.success(f"✅ Saved example as {filename}")
                log_audit_event("Style Example Uploaded", {
                    "filename": filename,
                    "tenant_id": tenant_id,
                    "module": "style_transfer"
                })
                st.rerun()
        except Exception as e:
            msg = handle_error(e, code="STYLE_UI_003")
            st.error(msg)

    # Input method: Excel or pasted text
    input_method = st.radio("📥 Select Input Method", ["Upload Excel", "Paste Text Inputs"])
    inputs_df = None

    if input_method == "Upload Excel":
        uploaded_file = st.file_uploader("📤 Upload Excel File", type=["xlsx"])
        input_col = st.text_input("🔎 Column to Rewrite", value="Input")
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                if input_col not in df.columns:
                    st.error(f"Column '{input_col}' not found in uploaded file.")
                else:
                    inputs_df = df[[input_col]].rename(columns={input_col: "Input"})
            except Exception as e:
                msg = handle_error(e, code="STYLE_UI_004")
                st.error(msg)

    elif input_method == "Paste Text Inputs":
        pasted_text = st.text_area("📋 Paste Inputs Here (separate with '---')", height=300)
        if pasted_text.strip():
            input_list = [x.strip() for x in pasted_text.split('---') if x.strip()]
            inputs_df = pd.DataFrame({"Input": input_list})

    # Generate outputs
    if inputs_df is not None and not inputs_df.empty and example_list and st.button("🔄 Generate Styled Outputs", key="generate_button_main"):
        with st.spinner("Generating styled outputs..."):
            try:
                check_quota("openai_tokens", amount=len(inputs_df))
                result_df = asyncio.run(run_batch_style_transfer(example_list, inputs_df, input_col="Input"))
                decrement_quota("openai_tokens", amount=len(result_df))
                st.success(f"✅ Successfully rewrote {len(result_df)} inputs.")
                st.dataframe(result_df)

                buffer = BytesIO()
                result_df.to_excel(buffer, index=False, engine='openpyxl')
                buffer.seek(0)

                st.download_button(
                    "📥 Download Results as Excel",
                    data=buffer,
                    file_name="styled_outputs.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                log_audit_event("Style Transfer Generated", {
                    "tenant_id": tenant_id,
                    "input_count": len(result_df),
                    "example_used": selected_example if selected_example != "None" else "pasted",
                    "module": "style_transfer"
                })
            except Exception as e:
                msg = handle_error(e, code="STYLE_UI_005")
                st.error(msg)

    elif st.button("🔄 Generate Styled Outputs", key="generate_button_fallback"):
        st.warning("Please provide both example paragraphs and at least one input.")
