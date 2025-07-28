import streamlit as st
import os
import hashlib
import asyncio
from datetime import datetime

from core.session_utils import get_session_temp_dir
from core.security import sanitize_text, sanitize_filename, redact_log, mask_phi
from services.foia_service import generate_foia_request
from core.usage_tracker import log_usage, check_quota, decrement_quota
from core.auth import get_user_id, get_tenant_id, get_user_role
from core.audit import log_audit_event
from logger import logger
from utils.file_utils import clean_temp_dir
from core.foia_constants import STATE_CITATIONS, STATE_RESPONSE_TIMES
from core.cache_utils import clear_caches
from core.error_handling import handle_error

clean_temp_dir()

def stream_file(path: str):
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk

def run_ui():
    st.header("📬 FOIA Letter Generator")

    try:
        st.subheader("🎨 Optional Style Example")
        example_text = ""
        tenant_id = get_tenant_id()
        EXAMPLE_DIR = os.path.join("examples", tenant_id, "foia")
        os.makedirs(EXAMPLE_DIR, exist_ok=True)

        example_files = sorted([f for f in os.listdir(EXAMPLE_DIR) if f.endswith(".txt")])
        selected_example = "None"
        if example_files:
            selected_example = st.selectbox("Choose Style Example", ["None"] + example_files)
            if selected_example != "None":
                path = os.path.join(EXAMPLE_DIR, selected_example)
                with open(path, "r", encoding="utf-8") as f:
                    example_text = f.read()
                with st.expander("🧠 Preview Example Text"):
                    st.code(example_text[:3000])
        else:
            st.info(f"No style examples found for FOIA in `{EXAMPLE_DIR}`")

        TEMPLATE_DIR = os.path.join("templates", tenant_id, "foia")
        os.makedirs(TEMPLATE_DIR, exist_ok=True)

        available_templates = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".docx")]
        if available_templates:
            selected_template = st.selectbox("📂 Choose FOIA Template", available_templates)
            TEMPLATE_FOIA = os.path.join(TEMPLATE_DIR, selected_template)
        else:
            st.warning("⚠️ No FOIA templates found. Please upload one in Template Manager.")
            TEMPLATE_FOIA = None

        with st.form("foia_form"):
            st.subheader("📌 Basic Info")
            client_id = st.text_input("Client ID")
            recipient_name = st.text_input("Recipient Name")
            recipient_abbrev = st.text_input("Recipient Abbreviation (for file name)")
            recipient_address_1 = st.text_input("Recipient Address Line 1")
            recipient_address_2 = st.text_input("Recipient Address Line 2 (City, State, Zip)")

            state = st.selectbox("State", list(STATE_CITATIONS.keys()))

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

        if submitted:
            clear_caches()

            if not TEMPLATE_FOIA:
                st.error("❌ You must select or upload a FOIA template in Template Manager before generating letters.")
                return

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
                    "formatted_date": datetime.today().strftime("%B %d, %Y"),
                    "client_id": sanitize_text(client_id),
                    "recipient_name": sanitize_text(recipient_name),
                    "recipient_address_1": sanitize_text(recipient_address_1),
                    "recipient_address_2": sanitize_text(recipient_address_2),
                    "recipient_abbrev": sanitize_text(recipient_abbrev),
                    "location": sanitize_text(location),
                    "doi": date_of_incident.strftime("%B %d, %Y"),
                    "synopsis": sanitize_text(case_synopsis),
                    "potential_requests": sanitize_text(potential_requests),
                    "explicit_instructions": sanitize_text(explicit_instructions),
                    "case_type": sanitize_text(case_type),
                    "facility_system": sanitize_text(facility_system),
                    "recipient_role": sanitize_text(recipient_role),
                    "state": sanitize_text(state),
                    "state_citation": STATE_CITATIONS.get(state, ""),
                    "state_response_time": STATE_RESPONSE_TIMES.get(state, ""),
                }

                logger.debug(mask_phi(f"🧾 FOIA form data payload: {data}"))

                fingerprint = "|".join([
                    data["client_id"],
                    data["recipient_abbrev"],
                    data["recipient_name"],
                    data["synopsis"],
                    example_text.strip()[:100]
                ])
                form_key = hashlib.md5(fingerprint.encode()).hexdigest()

                if "foia_cache" not in st.session_state:
                    st.session_state.foia_cache = {}

                if form_key in st.session_state.foia_cache:
                    file_path, metadata = st.session_state.foia_cache[form_key]
                    bullet_list = metadata.get("bullet_list", [])
                else:
                    with st.spinner("📄 Generating FOIA letter..."):
                        check_quota("foia_letters", amount=1)
                        temp_dir = get_session_temp_dir()
                        output_filename = sanitize_filename(
                            f"FOIA_{data['client_id']}_{datetime.today().strftime('%Y-%m-%d')}.docx"
                        )
                        file_path = os.path.join(temp_dir, output_filename)

                        bullet_list = asyncio.run(generate_foia_request(
                            data=data,
                            template_path=TEMPLATE_FOIA,
                            output_path=file_path,
                            example_text=example_text
                        ))[2]

                        decrement_quota("foia_letters", amount=1)
                        st.session_state.foia_cache[form_key] = (file_path, {"bullet_list": bullet_list})

                st.success("✅ FOIA letter generated!")
                with open(file_path, "rb") as f:
                    docx_bytes = f.read()

                st.subheader("📋 FOIA Request Bullet Points (Plain Text)")
                st.text_area(
                    label="Copyable Bullet List",
                    value="\n".join(f"• {line}" for line in bullet_list),
                    height=300
                )

                st.download_button(
                    label="⬇️ Download Letter (.docx)",
                    data=docx_bytes,
                    file_name=os.path.basename(file_path),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

                try:
                    log_usage(
                        event_type="foia_generated",
                        tenant_id=tenant_id,
                        user_id=get_user_id(),
                        count=1,
                        metadata={"client_id": client_id, "recipient": recipient_name}
                    )
                except Exception as log_err:
                    logger.warning(redact_log(mask_phi(f"⚠️ Failed to log FOIA usage: {log_err}")))

                try:
                    log_audit_event("FOIA Letter Generated", {
                        "client_id": client_id,
                        "recipient_name": recipient_name,
                        "case_type": case_type,
                        "facility_system": facility_system,
                        "used_example": selected_example if example_text else "None",
                        "used_template": selected_template,
                        "module": "foia"
                    })

                    log_audit_event("FOIA Template Used", {
                        "template": selected_template,
                        "example_used": selected_example if example_text else "None",
                        "tenant_id": tenant_id,
                        "module": "foia"
                    })

                except Exception as audit_err:
                    logger.warning(
                        redact_log(mask_phi(f"⚠️ Failed to write audit log: {audit_err}"))
                    )

            except Exception as e:
                msg = handle_error(e, code="FOIA_UI_001")
                st.error(msg)

                fallback_path = file_path.replace(".docx", "_FAILED.txt") if 'file_path' in locals() else None
                if fallback_path and os.path.exists(fallback_path):
                    with open(fallback_path, "r", encoding="utf-8") as f:
                        fallback_contents = f.read()

                    st.warning("⚠️ FOIA DOCX failed to render. Fallback debug output below:")
                    st.text_area("📝 Fallback .txt Output", value=fallback_contents, height=400)

                    st.download_button(
                        label="⬇️ Download Debug Output (.txt)",
                        data=fallback_contents,
                        file_name=os.path.basename(fallback_path),
                        mime="text/plain"
                    )

    except Exception as outer_e:
        msg = handle_error(outer_e, code="FOIA_UI_002")
        st.error(msg)