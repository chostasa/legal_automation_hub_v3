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

# 🧹 Clean temp dir at startup
clean_temp_dir()

def stream_file(path: str):
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk

def run_ui():
    st.header("📬 FOIA Letter Generator")

    with st.form("foia_form"):
        client_name = st.text_input("Client Name")
        agency_name = st.text_input("Agency / Facility Name")
        date_of_incident = st.date_input("Date of Incident")
        case_summary = st.text_area("Case Summary or Request Details")
        submitted = st.form_submit_button("⚙️ Generate FOIA Letter")

    if "foia_cache" not in st.session_state:
        st.session_state.foia_cache = {}

    if submitted:
        # 🚨 Validation
        errors = []
        if not client_name.strip():
            errors.append("Client name is required.")
        if not agency_name.strip():
            errors.append("Agency name is required.")
        if not case_summary.strip():
            errors.append("Summary is required.")
        if errors:
            for msg in errors:
                st.error(f"❌ {msg}")
            return

        try:
            # 🔐 Sanitize inputs
            sanitized_client = sanitize_text(client_name)
            sanitized_agency = sanitize_text(agency_name)
            sanitized_summary = sanitize_text(case_summary)
            formatted_doi = date_of_incident.strftime("%B %d, %Y")

            # 🧬 Build cache key
            fingerprint = "|".join([sanitized_client, sanitized_agency, sanitized_summary, formatted_doi])
            form_key = hashlib.md5(fingerprint.encode()).hexdigest()

            if form_key in st.session_state.foia_cache:
                file_path, _ = st.session_state.foia_cache[form_key]
            else:
                with st.spinner("🧠 Generating FOIA letter..."):
                    if not TEMPLATE_FOIA.lower().endswith(".docx"):
                        st.error("❌ The FOIA template must be a .docx file.")
                        return

                    temp_dir = get_secure_temp_dir()
                    output_filename = sanitize_filename(
                        f"FOIA_{sanitized_client}_{datetime.today().strftime('%Y-%m-%d')}.docx"
                    )
                    file_path = os.path.join(temp_dir, output_filename)

                    _, _ = generate_foia_request(
                        client_name=sanitized_client,
                        agency_name=sanitized_agency,
                        details=sanitized_summary,
                        template_path=TEMPLATE_FOIA,
                        output_path=file_path
                    )

                    st.session_state.foia_cache[form_key] = (file_path, {})

            # ✅ Output
            st.success("✅ FOIA letter generated!")
            st.download_button(
                label="⬇️ Download Letter (.docx)",
                data=stream_file(file_path),
                file_name=os.path.basename(file_path),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

            # 📈 Log usage
            try:
                log_usage(
                    event_type="foia_generated",
                    tenant_id=get_tenant_id(),
                    user_id=get_user_id(),
                    count=1,
                    metadata={"client_name": sanitized_client, "agency": sanitized_agency}
                )
            except Exception as log_err:
                logger.warning(f"⚠️ Failed to log FOIA usage: {log_err}")

            # 🛡️ Log audit
            try:
                log_audit_event("FOIA Letter Generated", {
                    "client_name": sanitized_client,
                    "agency_name": sanitized_agency,
                    "date_of_incident": formatted_doi,
                    "module": "foia"
                })
            except Exception as audit_err:
                logger.warning(f"⚠️ Failed to write audit log: {audit_err}")

        except Exception as e:
            logger.error(redact_log(f"❌ FOIA letter generation failed: {e}"))
            st.error("❌ An unexpected error occurred while generating the FOIA letter.")
