import streamlit as st
import os
import hashlib
from datetime import datetime

from core.session import get_secure_temp_dir
from core.security import sanitize_text, sanitize_filename, redact_log
from core.constants import foia_template as TEMPLATE_FOIA
from services.foia_service import generate_foia_request
from core.usage_tracker import log_usage
from core.auth import get_user_id, get_tenant_id
from core.audit import log_audit_event
from logger import logger
from utils.file_utils import clean_temp_dir

clean_temp_dir()

def stream_file(path: str):
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk

def run_ui():
    st.header("📬 FOIA Letter Generator")

    with st.form("foia_form"):
        st.subheader("📌 Basic Info")
        client_id = st.text_input("Client ID")
        recipient_name = st.text_input("Recipient Name")
        recipient_abbrev = st.text_input("Recipient Abbreviation (for file name)")
        recipient_address_1 = st.text_input("Recipient Address Line 1")
        recipient_address_2 = st.text_input("Recipient Address Line 2 (City, State, Zip)")

        st.subheader("📅 Incident Details")
        date_of_incident = st.date_input("Date of Incident")
        location = st.text_input("Location of Incident")

        st.subheader("🧾 Case Content")
        case_synopsis = st.text_area("Case Synopsis", height=150)
        potential_requests = st.text_area("Potential Requests", height=120)
        explicit_instructions = st.text_area("Explicit Instructions (optional)", height=100)

        st.subheader("📂 Classification")
        case_type = st.text_input("Case Type")
        facility_system = st.text_input("Facility or System")
        recipient_role = st.text_input("Recipient Role")

        submitted = st.form_submit_button("⚙️ Generate FOIA Letter")

    if "foia_cache" not in st.session_state:
        st.session_state.foia_cache = {}

    if submitted:
        # Validate required fields
        required_fields = {
            "Client ID": client_id,
            "Recipient Name": recipient_name,
            "Recipient Abbreviation": recipient_abbrev,
            "Recipient Address Line 1": recipient_address_1,
            "Recipient Address Line 2": recipient_address_2,
            "Date of Incident": date_of_incident,
            "Location": location,
            "Case Synopsis": case_synopsis,
            "Potential Requests": potential_requests,
            "Case Type": case_type,
            "Facility/System": facility_system,
            "Recipient Role": recipient_role
        }

        errors = [f"{key} is required." for key, value in required_fields.items() if not str(value).strip()]
        if errors:
            for msg in errors:
                st.error(f"❌ {msg}")
            return

        try:
            data = {
                "client_id": sanitize_text(client_id),
                "recipient_name": sanitize_text(recipient_name),
                "recipient_abbrev": sanitize_text(recipient_abbrev),
                "recipient_address_1": sanitize_text(recipient_address_1),
                "recipient_address_2": sanitize_text(recipient_address_2),
                "date_of_incident": date_of_incident.strftime("%B %d, %Y"),
                "location": sanitize_text(location),
                "case_synopsis": sanitize_text(case_synopsis),
                "potential_requests": sanitize_text(potential_requests),
                "explicit_instructions": sanitize_text(explicit_instructions),
                "case_type": sanitize_text(case_type),
                "facility_system": sanitize_text(facility_system),
                "recipient_role": sanitize_text(recipient_role)
            }

            fingerprint = "|".join([data["client_id"], data["recipient_abbrev"], data["recipient_name"], data["case_synopsis"]])
            form_key = hashlib.md5(fingerprint.encode()).hexdigest()

            if form_key in st.session_state.foia_cache:
                file_path, _ = st.session_state.foia_cache[form_key]
            else:
                with st.spinner("📄 Generating FOIA letter..."):
                    temp_dir = get_secure_temp_dir()
                    output_filename = sanitize_filename(
                        f"FOIA_{data['recipient_abbrev']}_{datetime.today().strftime('%Y-%m-%d')}.docx"
                    )
                    file_path = os.path.join(temp_dir, output_filename)

                    _, _ = generate_foia_request(
                        data=data,
                        template_path=TEMPLATE_FOIA,
                        output_path=file_path
                    )

                    st.session_state.foia_cache[form_key] = (file_path, {})

            st.success("✅ FOIA letter generated!")
            with open(file_path, "rb") as f:
                docx_bytes = f.read()

            st.download_button(
                label="⬇️ Download Letter (.docx)",
                data=docx_bytes,  # ✅ raw bytes
                file_name=os.path.basename(file_path),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

            # Log usage
            try:
                log_usage(
                    event_type="foia_generated",
                    tenant_id=get_tenant_id(),
                    user_id=get_user_id(),
                    count=1,
                    metadata={"client_id": client_id, "recipient": recipient_name}
                )
            except Exception as log_err:
                logger.warning(f"⚠️ Failed to log FOIA usage: {log_err}")

            # Audit log
            try:
                log_audit_event("FOIA Letter Generated", {
                    "client_id": client_id,
                    "recipient_name": recipient_name,
                    "case_type": case_type,
                    "facility_system": facility_system,
                    "module": "foia"
                })
            except Exception as audit_err:
                logger.warning(f"⚠️ Failed to write audit log: {audit_err}")

        except Exception as e:
            logger.error(redact_log(f"❌ FOIA letter generation failed: {e}"))
            st.error("❌ An unexpected error occurred while generating the FOIA letter.")
