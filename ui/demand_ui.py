import streamlit as st
import os
import hashlib
from datetime import datetime

from core.session import get_secure_temp_dir
from core.security import sanitize_text, sanitize_filename, redact_log
from core.constants import demand_template as TEMPLATE_DEMAND
from services.demand_service import generate_demand_letter
from core.usage_tracker import log_usage
from core.auth import get_user_id, get_tenant_id
from core.audit import log_audit_event
from logger import logger

from utils.file_utils import clean_temp_dir
clean_temp_dir()

EXAMPLE_DIR = os.path.join("examples", "demand", get_tenant_id())
os.makedirs(EXAMPLE_DIR, exist_ok=True)

def load_binary_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def run_ui():
    st.header("📂 Demand Letter Generator")

    # === Optional: Select AI Style Example ===
    st.markdown("### 🎨 Optional: Style / Tone Example")
    example_text = ""
    example_files = sorted([f for f in os.listdir(EXAMPLE_DIR) if f.endswith(".txt")])
    if example_files:
        selected_example = st.selectbox("Choose Example to Apply Style", ["None"] + example_files)
        if selected_example != "None":
            path = os.path.join(EXAMPLE_DIR, selected_example)
            with open(path, "r", encoding="utf-8") as f:
                example_text = f.read()
            with st.expander("🧠 Preview Example Text"):
                st.code(example_text[:3000], language="markdown")
    else:
        st.info("No style examples found in examples/demand/{tenant_id}/")

    # === Main Form ===
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

        if errors:
            for msg in errors:
                st.error(f"❌ {msg}")
            return

        try:
            # 🔐 Sanitize
            full_name = sanitize_text(client_name)
            formatted_date = incident_date.strftime("%B %d, %Y")
            summary = sanitize_text(summary)
            damages = sanitize_text(damages)
            defendant = sanitize_text(defendant)
            location = sanitize_text(location)

            fingerprint = "|".join([
                full_name, formatted_date, summary, damages, example_text.strip()[:100]
            ])
            form_key = hashlib.md5(fingerprint.encode()).hexdigest()

            if form_key in st.session_state.demand_cache:
                file_path, _ = st.session_state.demand_cache[form_key]
            else:
                with st.spinner("🧠 Generating demand letter..."):
                    temp_dir = get_secure_temp_dir()
                    output_filename = sanitize_filename(
                        f"Demand_{full_name}_{datetime.today().strftime('%Y-%m-%d')}.docx"
                    )
                    file_path = os.path.join(temp_dir, output_filename)

                    if not TEMPLATE_DEMAND.lower().endswith(".docx"):
                        st.error("❌ The demand template must be a .docx file.")
                        return

                    _, _ = generate_demand_letter(
                        client_name=full_name,
                        defendant=defendant,
                        location=location,
                        incident_date=formatted_date,
                        summary=summary,
                        damages=damages,
                        template_path=TEMPLATE_DEMAND,
                        output_path=file_path,
                        example_text=example_text
                    )

                    st.session_state.demand_cache[form_key] = (file_path, {})

            # ✅ Output
            st.success("✅ Demand letter generated!")
            st.download_button(
                "⬇️ Download Demand Letter (.docx)",
                data=load_binary_file(file_path),
                file_name=os.path.basename(file_path),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )


            # 📈 Log usage
            try:
                log_usage(
                    event_type="demand_generated",
                    tenant_id=get_tenant_id(),
                    user_id=get_user_id(),
                    count=1,
                    metadata={"client_name": full_name}
                )
            except Exception as log_err:
                logger.warning(f"⚠️ Failed to log demand usage: {log_err}")

            # 🛡️ Log audit event
            try:
                log_audit_event("Demand Letter Generated", {
                    "client_name": full_name,
                    "incident_date": formatted_date,
                    "used_example": selected_example if example_text else "None",
                    "module": "demand"
                })
            except Exception as audit_err:
                logger.warning(f"⚠️ Failed to write audit log: {audit_err}")

        except Exception as e:
            logger.error(redact_log(f"❌ Demand letter generation failed: {e}"))
            st.error("❌ An unexpected error occurred while generating the demand letter.")
