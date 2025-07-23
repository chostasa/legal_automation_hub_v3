import streamlit as st
import os
import hashlib

from utils.file_utils import clean_temp_dir
clean_temp_dir()

from core.session import get_secure_temp_dir
from core.security import sanitize_text, redact_log
from core.audit import log_audit_event
from logger import logger
from services.memo_service import (
    generate_quotes_from_raw_depo,
    generate_memo_from_fields,
    generate_plaintext_memo
)

error_code = "MEMO_GEN_001"

def stream_file(path: str):
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk

def run_ui():
    st.header("🧾 Mediation Memo Generator")

    with st.form("mediation_form"):
        st.subheader("Case Details")
        court = st.text_input("Court", value="Circuit Court of Cook County, Illinois")
        case_number = st.text_input("Case Number")

        st.subheader("Plaintiff(s)")
        plaintiffs = [st.text_input(f"Plaintiff {i}", key=f"p{i}") for i in range(1, 4)]

        st.subheader("Defendant(s)")
        defendants = [st.text_input(f"Defendant {i}", key=f"d{i}") for i in range(1, 8)]

        st.subheader("Narratives & Facts")
        complaint_narrative = st.text_area("📄 Complaint Narrative", height=200)
        party_info = st.text_area("👤 Party Information (from Complaint)", height=150)
        settlement_summary = st.text_area("💰 Settlement Summary", height=150)
        medical_summary = st.text_area("🏥 Medical Summary", height=200)

        st.subheader("Deposition Excerpts (Optional)")
        raw_depo = st.text_area("📑 Paste Deposition Transcript (with line #s)", height=250)
        quote_categories = st.multiselect(
            "Quote Categories to Extract",
            options=["Liability", "Damages", "Additional Harms", "Facts", "Causation"],
            default=["Liability", "Damages"]
        )

        st.subheader("Template")
        uploaded_template = st.file_uploader("Upload Mediation Memo Template (.docx)", type=["docx"])

        st.subheader("🧠 Optional Style Example")
        example_text = st.text_area("📘 Paste Example for Style/Tone Matching (optional)", height=120)

        submitted = st.form_submit_button("⚙️ Generate Mediation Memo")

    if "memo_cache" not in st.session_state:
        st.session_state.memo_cache = {}

    if submitted:
        errors = []

        if not uploaded_template or not uploaded_template.name.endswith(".docx"):
            errors.append("Uploaded template must be a .docx file.")
        if not court.strip():
            errors.append("Court name is required.")
        if not case_number.strip():
            errors.append("Case number is required.")
        if not complaint_narrative.strip():
            errors.append("Complaint narrative is required.")
        if not settlement_summary.strip():
            errors.append("Settlement summary is required.")
        if not medical_summary.strip():
            errors.append("Medical summary is required.")

        valid_plaintiffs = [p for p in plaintiffs if p.strip()]
        valid_defendants = [d for d in defendants if d.strip()]
        if not valid_plaintiffs:
            errors.append("At least one valid plaintiff name is required.")
        if not valid_defendants:
            errors.append("At least one valid defendant name is required.")

        if errors:
            for msg in errors:
                st.error(f"❌ {msg}")
            return

        try:
            input_fingerprint = "|".join([
                court, case_number, complaint_narrative, party_info,
                settlement_summary, medical_summary, raw_depo,
                ",".join(plaintiffs), ",".join(defendants), ",".join(quote_categories),
                example_text
            ])
            form_key = hashlib.md5(input_fingerprint.encode()).hexdigest()

            if form_key in st.session_state.memo_cache:
                file_path, memo_data, raw_quotes = st.session_state.memo_cache[form_key]
            else:
                with st.spinner("🔄 Generating memo..."):

                    raw_quotes = {}
                    if raw_depo:
                        raw_quotes = generate_quotes_from_raw_depo(raw_depo, quote_categories)

                    data = {
                        "court": sanitize_text(court),
                        "case_number": sanitize_text(case_number),
                        "complaint_narrative": sanitize_text(complaint_narrative),
                        "party_information_from_complaint": sanitize_text(party_info),
                        "settlement_summary": sanitize_text(settlement_summary),
                        "medical_summary": sanitize_text(medical_summary),
                        "plaintiffs": ", ".join([sanitize_text(p) for p in valid_plaintiffs]),
                        "defendants": ", ".join([sanitize_text(d) for d in valid_defendants]),
                        "example_text": sanitize_text(example_text)
                    }

                    for key, value in raw_quotes.items():
                        data[key] = sanitize_text(value)

                    for i, name in enumerate(plaintiffs, 1):
                        data[f"plaintiff{i}"] = sanitize_text(name)
                    for i, name in enumerate(defendants, 1):
                        data[f"defendant{i}"] = sanitize_text(name)

                    temp_dir = get_secure_temp_dir()
                    file_path, memo_data = generate_memo_from_fields(
                        data=data,
                        template_path=uploaded_template,
                        output_dir=temp_dir
                    )

                    st.session_state.memo_cache[form_key] = (file_path, memo_data, raw_quotes)

            st.success("✅ Memo generated successfully!")
            st.download_button(
                label="⬇️ Download Mediation Memo (.docx)",
                data=stream_file(file_path),
                file_name=os.path.basename(file_path),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

            txt_preview = generate_plaintext_memo(memo_data)
            st.download_button(
                label="📄 Download Plain Text Preview",
                data=txt_preview,
                file_name=os.path.basename(file_path).replace(".docx", ".txt"),
                mime="text/plain"
            )

            for key, value in raw_quotes.items():
                if value.strip():
                    label = key.replace("_quotes", "").replace("_", " ").title()
                    icon = "💥" if "damage" in key.lower() else "🧾"
                    with st.expander(f"{icon} {label} Quotes Extracted"):
                        for q in value.strip().split("\n\n"):
                            st.markdown(f"- {q.strip()}")

            from core.usage_tracker import log_usage
            from core.auth import get_user_id, get_tenant_id

            try:
                log_usage(
                    event_type="memo_generated",
                    tenant_id=get_tenant_id(),
                    user_id=get_user_id(),
                    count=1,
                    metadata={
                        "court": court,
                        "plaintiffs": valid_plaintiffs,
                        "defendants": valid_defendants,
                        "quote_categories": quote_categories
                    }
                )
            except Exception as log_err:
                logger.warning(f"⚠️ Failed to log memo usage: {log_err}")

            try:
                log_audit_event("Mediation Memo Generated", {
                    "court": court,
                    "case_number": case_number,
                    "plaintiffs": valid_plaintiffs,
                    "defendants": valid_defendants,
                    "module": "mediation"
                })
            except Exception as audit_err:
                logger.warning(f"⚠️ Failed to write audit log: {audit_err}")

        except Exception as e:
            logger.error(redact_log(f"[{error_code}] ❌ Mediation memo generation failed: {e}"))
            st.error(f"❌ An unexpected error occurred (code: {error_code}). Please contact support.")
