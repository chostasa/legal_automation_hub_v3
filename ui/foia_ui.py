import streamlit as st
import os
import hashlib
from datetime import datetime

from core.session import get_secure_temp_dir
from core.security import sanitize_text, sanitize_filename, redact_log
from core.constants import foia_template as TEMPLATE_FOIA
from core.generators.foia import generate_foia_sections
from utils.docx_utils import replace_text_in_docx_all
from logger import logger

def stream_file(path: str):
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk

def run_ui():
    st.header("📬 FOIA Letter Generator")

    with st.form("foia_form"):
        client_id = st.text_input("Client ID")
        defendant_name = st.text_input("Recipient Name")
        address_line1 = st.text_input("Recipient Address Line 1")
        address_line2 = st.text_input("Recipient Address Line 2 (City, State, Zip)")
        date_of_incident = st.date_input("Date of Incident")
        location = st.text_input("Location of Incident")

        case_synopsis = st.text_area("Case Synopsis")
        potential_requests = st.text_area("Potential Requests (optional)")
        explicit_instructions = st.text_area("Explicit Instructions (optional)")
        case_type = st.text_input("Case Type")
        facility = st.text_input("Facility or System")
        defendant_role = st.text_input("Recipient Role")

        submitted = st.form_submit_button("⚙️ Generate FOIA Letter")

    if "foia_cache" not in st.session_state:
        st.session_state.foia_cache = {}

    if submitted:
        errors = []

        if not client_id.strip():
            errors.append("Client ID is required.")
        if not defendant_name.strip():
            errors.append("Recipient name is required.")
        if not case_synopsis.strip():
            errors.append("Case synopsis is required.")

        if errors:
            for msg in errors:
                st.error(f"❌ {msg}")
            return

        try:
            # 🔐 Sanitize all fields
            client_id_safe = sanitize_text(client_id)
            defendant_name = sanitize_text(defendant_name)
            address_line1 = sanitize_text(address_line1)
            address_line2 = sanitize_text(address_line2)
            location = sanitize_text(location)
            case_synopsis = sanitize_text(case_synopsis)
            potential_requests = sanitize_text(potential_requests)
            explicit_instructions = sanitize_text(explicit_instructions)
            case_type = sanitize_text(case_type)
            facility = sanitize_text(facility)
            defendant_role = sanitize_text(defendant_role)

            # 🔑 Caching key
            fingerprint = "|".join([
                client_id_safe, defendant_name, address_line1, address_line2, location,
                case_synopsis, potential_requests, explicit_instructions, case_type,
                facility, defendant_role
            ])
            form_key = hashlib.md5(fingerprint.encode()).hexdigest()

            if form_key in st.session_state.foia_cache:
                file_path, replacements = st.session_state.foia_cache[form_key]
            else:
                with st.spinner("🧠 Generating FOIA letter..."):
                    # 🤖 GPT content
                    sections = generate_foia_sections(
                        case_synopsis=case_synopsis,
                        case_type=case_type,
                        facility=facility,
                        defendant_role=defendant_role,
                        potential_requests=potential_requests,
                        explicit_instructions=explicit_instructions,
                    )

                    replacements = {
                        "client_id": client_id_safe,
                        "date": datetime.today().strftime("%B %d, %Y"),
                        "defendant_name": defendant_name,
                        "defendant_line1": address_line1,
                        "defendant_line2": address_line2,
                        "doi": date_of_incident.strftime("%B %d, %Y"),
                        "location": location,
                        "synopsis": sections["synopsis"],
                        "foia_request_bullet_points": sections["foia_request_bullet_points"],
                    }

                    if not TEMPLATE_FOIA.lower().endswith(".docx"):
                        st.error("❌ The FOIA template must be a .docx file.")
                        return

                    # 💾 Save to file
                    temp_dir = get_secure_temp_dir()
                    output_filename = sanitize_filename(
                        f"FOIA_{client_id_safe}_{datetime.today().strftime('%Y-%m-%d')}.docx"
                    )
                    file_path = os.path.join(temp_dir, output_filename)

                    replace_text_in_docx_all(TEMPLATE_FOIA, replacements, file_path)
                    st.session_state.foia_cache[form_key] = (file_path, replacements)

            st.success("✅ FOIA letter generated!")
            st.download_button(
                label="⬇️ Download Letter (.docx)",
                data=stream_file(file_path),
                file_name=os.path.basename(file_path),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        except Exception as e:
            logger.error(redact_log(f"❌ FOIA letter generation failed: {e}"))
            st.error("❌ An unexpected error occurred while generating the FOIA letter.")
