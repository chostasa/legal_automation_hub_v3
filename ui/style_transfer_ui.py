import streamlit as st
import pandas as pd
from io import BytesIO
from services.style_transfer_service import run_batch_style_transfer

def run_style_transfer_ui():
    st.title("🧠 Style Mimic Generator")
    st.markdown("""
Upload one or more **example paragraphs**, then either upload an Excel file of inputs **or** paste them directly into the app.
Each input will be rewritten to match the **tone, structure, and legal voice** of the example(s).

- Separate multiple example paragraphs with `---`
- Pasted inputs should also be separated with `---`
""")

    # === Example paragraph input ===
    example_input = st.text_area("✍️ Paste Example Paragraph(s) (separate with '---')", height=250)
    example_list = [p.strip() for p in example_input.split("---") if p.strip()]

    # === Input method ===
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
                st.error(f"❌ Failed to read Excel file: {str(e)}")

    elif input_method == "Paste Text Inputs":
        pasted_text = st.text_area("📋 Paste Inputs Here (separate with '---')", height=300)
        if pasted_text.strip():
            input_list = [x.strip() for x in pasted_text.split('---') if x.strip()]
            inputs_df = pd.DataFrame({"Input": input_list})

    # === Generate Styled Outputs ===
    if inputs_df is not None and not inputs_df.empty and example_list and st.button("🔄 Generate Styled Outputs", key="generate_button_main"):
        with st.spinner("Generating styled outputs..."):
            result_df = run_batch_style_transfer(example_list, inputs_df, input_col="Input")
            st.success(f"✅ Successfully rewrote {len(result_df)} inputs.")
            st.dataframe(result_df)

            # Convert to Excel in memory
            buffer = BytesIO()
            result_df.to_excel(buffer, index=False, engine='openpyxl')
            buffer.seek(0)

            st.download_button(
                "📥 Download Results as Excel",
                data=buffer,
                file_name="styled_outputs.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    elif st.button("🔄 Generate Styled Outputs", key="generate_button_fallback"):
        st.warning("Please provide both example paragraphs and at least one input.")
