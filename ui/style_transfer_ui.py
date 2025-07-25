import streamlit as st
import pandas as pd
from services.style_transfer_service import run_batch_style_transfer

def run_style_transfer_ui():
    st.title("🧠 Style Mimic Generator")
    st.markdown("Upload example paragraphs, then batch rewrite your Excel data into that same tone and structure.")

    example_input = st.text_area("✍️ Paste Example Paragraph(s) (separate with '---')", height=250)

    uploaded_file = st.file_uploader("📤 Upload Excel File with Inputs", type=["xlsx"])
    input_col = st.text_input("🔎 Column Name to Rewrite (from your Excel)", value="Input")

    if uploaded_file and st.button("🔄 Generate Styled Outputs"):
        df = pd.read_excel(uploaded_file)
        if input_col not in df.columns:
            st.error(f"Column '{input_col}' not found.")
            return

        example_list = [p.strip() for p in example_input.split("---") if p.strip()]
        styled_df = run_batch_style_transfer(example_list, df, input_col)

        st.success(f"✅ Rewrote {len(styled_df)} rows.")
        st.dataframe(styled_df)

        st.download_button(
            "📥 Download Results as Excel",
            data=styled_df.to_excel(index=False),
            file_name="styled_outputs.xlsx"
        )
