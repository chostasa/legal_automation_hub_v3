import streamlit as st
import os
import hashlib
from datetime import datetime

from core.session_utils import get_session_temp_dir
from core.security import sanitize_text, sanitize_filename, redact_log, mask_phi
from core.constants import demand_template as TEMPLATE_DEMAND
from services.demand_service import generate_demand_letter
from core.usage_tracker import log_usage, check_quota, decrement_quota
from core.auth import get_user_id, get_tenant_id, get_user_role
from core.audit import log_audit_event
from logger import logger
from core.cache_utils import clear_caches
from core.error_handling import handle_error

from utils.file_utils import clean_temp_dir
clean_temp_dir()

EXAMPLE_DIR = os.path.join("examples", get_tenant_id(), "demand")
os.makedirs(EXAMPLE_DIR, exist_ok=True)

TEMPLATE_DIR = os.path.join("templates", get_tenant_id(), "demand")
os.makedirs(TEMPLATE_DIR, exist_ok=True)

def load_binary_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def run_ui():
    st.header("📂 Demand Letter Generator")

    st.markdown("### 🎨 Optional: Style / Tone Example")
    example_text = ""
    selected_example = None
    example_files = sorted([f for f in os.listdir(EXAMPLE_DIR) if f.endswith(".txt")])
    if example_files:
        selected_example = st.selectbox("Choose Example to Apply Style", ["None"] + example_files)
        if selected_example != "None":
            try:
                path = os.path.join(EXAMPLE_DIR, selected_example)
                with open(path, "r", encoding="utf-8") as f:
                    example_text = f.read()
                with st.expander("🧠 Preview Example Text"):
                    st.code(example_text[:3000], language="markdown")
            except Exception as e:
                msg = handle_error(e, code="DEMAND_UI_001")
                st.error(msg)
    else:
        st.info(f"No style examples found in {EXAMPLE_DIR}")

    st.markdown("### 📄 Select Demand Template")
    selected_template = None
    try:
        template_files = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".docx")]
        if template_files:
            selected_template = st.selectbox("Choose Template to Use", template_files)
        else:
            st.warning(f"No templates found in {TEMPLATE_DIR}. Please upload one in the Template Manager.")
    except Exception as e:
        msg = handle_error(e, code="DEMAND_UI_002")
        st.error(msg)

    with st.form("demand_form"):
        client_name = st.text_input("Client Name")
        defendant = st.text_input("Defendant Name")
        incident_date = st.date_input("Incident Date")
        location = st.text_input("Location of Incident")
        summary = st.text_area("Summary of Incident")
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
        if not defendant.strip():
            errors.append("Defendant name is required.")
        if not location.strip():
            errors.append("Incident location is required.")
        if not selected_template:
            errors.append("You must select a demand template from the Template Manager.")

        if errors:
            for msg in errors:
                st.error(f"❌ {msg}")
            return

        try:
            check_quota("demand_letters", amount=1)
            full_name = sanitize_text(client_name)
            formatted_date = incident_date.strftime("%B %d, %Y")
            summary = sanitize_text(summary)
            damages = sanitize_text(damages)
            defendant = sanitize_text(defendant)
            location = sanitize_text(location)

            fingerprint = "|".join([
                full_name, formatted_date, summary, damages, example_text.strip()[:100], selected_template
            ])
            form_key = hashlib.md5(fingerprint.encode()).hexdigest()

            if form_key in st.session_state.demand_cache:
                file_path, _ = st.session_state.demand_cache[form_key]
            else:
                with st.spinner("🧠 Generating demand letter..."):
                    temp_dir = get_session_temp_dir()
                    output_filename = sanitize_filename(
                        f"Demand_{full_name}_{datetime.today().strftime('%Y-%m-%d')}.docx"
                    )
                    file_path = os.path.join(temp_dir, output_filename)

                    template_path = os.path.join(TEMPLATE_DIR, selected_template)
                    if not template_path.lower().endswith(".docx"):
                        st.error("❌ The demand template must be a .docx file.")
                        return

                    clear_caches()

                    generate_demand_letter(
                        client_name=full_name,
                        defendant=defendant,
                        location=location,
                        incident_date=formatted_date,
                        summary=summary,
                        damages=damages,
                        template_path=template_path,
                        output_path=file_path,
                        example_text=example_text
                    )

                    st.session_state.demand_cache[form_key] = (file_path, {})

            decrement_quota("demand_letters", amount=1)
            st.success("✅ Demand letter generated!")
            st.download_button(
                "⬇️ Download Demand Letter (.docx)",
                data=load_binary_file(file_path),
                file_name=os.path.basename(file_path),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

            try:
                log_usage(
                    event_type="demand_generated",
                    tenant_id=get_tenant_id(),
                    user_id=get_user_id(),
                    count=1,
                    metadata={"client_name": full_name, "template_used": selected_template}
                )
            except Exception as log_err:
                logger.warning(redact_log(mask_phi(f"⚠️ Failed to log demand usage: {log_err}")))

            try:
                log_audit_event("Demand Letter Generated", {
                    "client_name": full_name,
                    "incident_date": formatted_date,
                    "used_example": selected_example if example_text else "None",
                    "used_template": selected_template,
                    "module": "demand"
                })
                log_audit_event("Demand Template Used", {
                    "template": selected_template,
                    "example_used": selected_example if example_text else "None",
                    "tenant_id": get_tenant_id(),
                    "module": "demand"
                })
            except Exception as audit_err:
                logger.warning(redact_log(mask_phi(f"⚠️ Failed to write audit log: {audit_err}")))

        except Exception as e:
            msg = handle_error(e, code="DEMAND_UI_003")
            st.error(msg)
