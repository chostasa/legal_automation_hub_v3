import streamlit as st
import os
import hashlib
from datetime import datetime

from core.session import get_secure_temp_dir
from core.security import sanitize_text, sanitize_filename, redact_log
from core.constants import demand_template as TEMPLATE_DEMAND
from core.generators.demand import generate_demand_sections
from utils.docx_utils import replace_text_in_docx_all
from logger import logger

def stream_file(path: str):
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk

def run_ui():
    st.header("📂 Demand Letter Generator")

    with st.form("demand_form"):
        client_name = st.text_input("Client Name")
        incident_date = st.date_input("Incident Date")
        summary = st.text_area("Incident Summary")
        damages = st.text_area("Damages Summary")
        submitted = st.form_submit_button("⚙️ Generate Demand Letter")

    if "demand_cache" not in st.session_state:
        st.session_state.demand_cache = {}

    if submitted:
        errors = []
        if not client_name.strip():
            errors.append("Client name is required.")
        if not summary.strip():
            errors.append("Incident summary is required.")
        if not damages.strip():
            errors.append("Damages summary is required.")

        if errors:
            for msg in errors:
                st.error(f"❌ {msg}")
            return

        try:
            # 🔐 Sanitize inputs
            full_name = sanitize_text(client_name)
            first_name = full_name.split()[0]
            formatted_date = incident_date.strftime("%B %d, %Y")
            summary = sanitize_text(summary)
            damages = sanitize_text(damages)

            # 🔑 Build input fingerprint for caching
            fingerprint = "|".join([
                full_name, formatted_date, summary, damages
            ])
            form_key = hashlib.md5(fingerprint.encode()).hexdigest()

            # 📦 Return cached file if available
            if form_key in st.session_state.demand_cache:
                file_path, replacements = st.session_state.demand_cache[form_key]
            else:
                with st.spinner("🧠 Generating demand letter..."):
                    # 🧠 GPT generation
                    sections = generate_demand_sections(full_name, first_name, summary, damages)

                    replacements = {
                        "Client Name": full_name,
                        "IncidentDate": formatted_date,
                        "Brief Synopsis": sections["brief_synopsis"],
                        "Demand": sections["demand"],
                        "Damages": sections["damages"],
                        "Settlement Demand": sections["settlement"],
                    }

                    temp_dir = get_secure_temp_dir()
                    output_filename = sanitize_filename(
                        f"Demand_{full_name}_{datetime.today().strftime('%Y-%m-%d')}.docx"
                    )
                    file_path = os.path.join(temp_dir, output_filename)

                    if not TEMPLATE_DEMAND.lower().endswith(".docx"):
                        st.error("❌ The demand template must be a .docx file.")
                        return

                    replace_text_in_docx_all(TEMPLATE_DEMAND, replacements, file_path)
                    st.session_state.demand_cache[form_key] = (file_path, replacements)

            st.success("✅ Demand letter generated!")

            st.download_button(
                "⬇️ Download Demand Letter (.docx)",
                data=stream_file(file_path),
                file_name=os.path.basename(file_path),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        except Exception as e:
            logger.error(redact_log(f"❌ Demand letter generation failed: {e}"))
            st.error("❌ An unexpected error occurred while generating the demand letter.")
