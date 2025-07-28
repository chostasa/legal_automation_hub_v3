import streamlit as st
import os
import hashlib
import json
import asyncio
from datetime import datetime

from utils.file_utils import clean_temp_dir, get_session_temp_dir, sanitize_filename
from core.session_utils import get_session_temp_dir as legacy_get_session_temp_dir
from core.security import sanitize_text, redact_log, mask_phi
from core.cache_utils import clear_caches
from core.audit import log_audit_event
from core.auth import get_tenant_id, get_user_role, get_user_id
from core.error_handling import handle_error
from core.usage_tracker import check_quota, decrement_quota, log_usage
from logger import logger
from utils.thread_utils import run_async
from services.memo_service import (
    generate_quotes_from_raw_depo,
    generate_memo_from_fields,
    generate_plaintext_memo
)
from services.dropbox_client import DropboxClient
from core.constants import DROPBOX_TEMPLATES_ROOT
from dropbox.files import WriteMode

# Clean only base tmp dir once
clean_temp_dir()

ERROR_CODE = "MEMO_GEN_001"


def stream_file(path: str):
    """Stream file in chunks for downloads."""
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            yield chunk


async def run_async_memo_generation(data, template_path, temp_dir):
    """Async wrapper for memo generation."""
    return await run_async(generate_memo_from_fields, data, template_path, temp_dir)


def run_ui():
    st.header("🗞 Mediation Memo Generator")

    try:
        tenant_id = get_tenant_id()
        user_id = get_user_id()
        role = get_user_role()
        client = DropboxClient()

        # Get list of saved templates/examples from Dropbox
        template_folder = f"{DROPBOX_TEMPLATES_ROOT}/mediation"
        available_templates = client.list_files(template_folder)

        example_folder = f"{DROPBOX_TEMPLATES_ROOT}/examples/mediation"
        available_examples = client.list_files(example_folder)

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
            future_medical_bills = st.text_area("📈 Future Medical Bills (optional)", height=150)

            st.subheader("Deposition Excerpts (Optional)")
            raw_depo = st.text_area("📁 Paste Deposition Transcript (with line #s)", height=250)
            quote_categories = st.multiselect(
                "Quote Categories to Extract",
                options=["Liability", "Damages", "Additional Harms", "Facts", "Causation"],
                default=["Liability", "Damages"]
            )

            # Template management: upload or use existing
            st.subheader("Template")
            template_choice = st.radio(
                "Select Template Source", ["Upload New Template", "Use Saved Template"]
            )

            uploaded_template = None
            selected_template_path = None

            if template_choice == "Upload New Template":
                uploaded_template = st.file_uploader("Upload Mediation Memo Template (.docx)", type=["docx"])
            else:
                if available_templates:
                    selected_template_name = st.selectbox("Select Saved Template", available_templates)
                    selected_template_path = client.download_file(
                        f"{template_folder}/{selected_template_name}", "templates_preview"
                    )
                else:
                    st.info("⚠️ No saved templates found for your firm. Please upload one.")
                    uploaded_template = st.file_uploader("Upload Mediation Memo Template (.docx)", type=["docx"])

            # Style example management
            st.subheader("🧠 Optional Style Example")
            example_text = ""
            selected_example_name = "None"

            if available_examples:
                selected_example_name = st.selectbox("Choose Style Example", ["None"] + available_examples)
                if selected_example_name != "None":
                    example_path = client.download_file(
                        f"{example_folder}/{selected_example_name}", "examples_preview"
                    )
                    with open(example_path, "r", encoding="utf-8") as f:
                        example_text = f.read()
                    with st.expander("🧠 Preview Example Text"):
                        st.code(example_text[:3000], language="markdown")
            else:
                st.info("No style examples available. Upload examples in Template Manager.")

            action = st.radio(
                "Choose Action", ["🔍 Preview Party Paragraphs", "📂 Generate Memo"]
            )

            submitted = st.form_submit_button("⚙️ Run")

        if "memo_cache" not in st.session_state:
            st.session_state.memo_cache = {}

        if not submitted:
            return

        errors = []
        template_path = None
        if template_choice == "Upload New Template":
            if not uploaded_template or not uploaded_template.name.endswith(".docx"):
                errors.append("Uploaded template must be a .docx file.")
        else:
            if not selected_template_path or not selected_template_path.endswith(".docx"):
                errors.append("You must select a saved template.")

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

        # Save uploaded template to Dropbox
        if template_choice == "Upload New Template" and uploaded_template:
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            versioned_name = f"{timestamp}_{sanitize_filename(uploaded_template.name)}"
            dropbox_path = f"{template_folder}/{versioned_name}"

            client.dbx.files_upload(
                uploaded_template.getvalue(), dropbox_path, mode=WriteMode.overwrite
            )

            log_audit_event("Mediation Template Uploaded", {
                "tenant_id": tenant_id,
                "template": versioned_name,
                "module": "mediation"
            })

            # Download to temp for generation
            template_path = client.download_file(dropbox_path, "templates_preview")
            clear_caches()
        else:
            template_path = selected_template_path

        # Cache key isolation includes tenant and user
        input_fingerprint = "|".join([
            tenant_id, user_id, court, case_number, complaint_narrative, party_info,
            settlement_summary, medical_summary, future_medical_bills, raw_depo,
            ",".join(plaintiffs), ",".join(defendants), ",".join(quote_categories),
            example_text, template_path or ""
        ])
        form_key = hashlib.md5(input_fingerprint.encode()).hexdigest()

        if form_key in st.session_state.memo_cache:
            file_path, memo_data, raw_quotes = st.session_state.memo_cache[form_key]
        else:
            with st.spinner("🔄 Processing..."):
                try:
                    check_quota("memo_generation", amount=1)

                    raw_quotes = generate_quotes_from_raw_depo(raw_depo, quote_categories) if raw_depo else {}

                    data = {
                        "court": sanitize_text(court),
                        "case_number": sanitize_text(case_number),
                        "complaint_narrative": sanitize_text(complaint_narrative),
                        "party_information_from_complaint": sanitize_text(party_info),
                        "settlement_summary": sanitize_text(settlement_summary),
                        "medical_summary": sanitize_text(medical_summary),
                        "future_medical_bills": sanitize_text(future_medical_bills),
                        "plaintiffs": ", ".join([sanitize_text(p) for p in valid_plaintiffs]),
                        "defendants": ", ".join([sanitize_text(d) for d in valid_defendants]),
                        "example_text": sanitize_text(example_text),
                    }

                    for key, value in raw_quotes.items():
                        data[key] = sanitize_text(value)

                    for i, name in enumerate(plaintiffs, 1):
                        data[f"plaintiff{i}"] = sanitize_text(name)
                    for i, name in enumerate(defendants, 1):
                        data[f"defendant{i}"] = sanitize_text(name)

                    temp_dir = get_session_temp_dir()
                    file_path, memo_data = asyncio.run(run_async_memo_generation(data, template_path, temp_dir))

                    st.session_state.memo_cache[form_key] = (file_path, memo_data, raw_quotes)
                    decrement_quota("memo_generation", amount=1)

                except Exception as e:
                    msg = handle_error(e, code=ERROR_CODE)
                    st.error(msg)
                    return

        # Party paragraph preview
        if action == "🔍 Preview Party Paragraphs":
            st.subheader("✏️ Review & Edit Party Paragraphs")
            if "party_edits" not in st.session_state:
                st.session_state.party_edits = {}

            for i in range(1, 4):
                key = f"Plaintiff_{i}"
                if memo_data.get(key):
                    st.session_state.party_edits[key] = st.text_area(
                        f"Plaintiff {i} Narrative", value=memo_data[key], height=150
                    )

            for i in range(1, 8):
                key = f"Defendant_{i}"
                if memo_data.get(key):
                    st.session_state.party_edits[key] = st.text_area(
                        f"Defendant {i} Narrative", value=memo_data[key], height=150
                    )

            st.info("💾 Your edits will be included when you select '📂 Generate Memo'.")
            return

        # Apply edits if preview was used
        if "party_edits" in st.session_state:
            for key, val in st.session_state.party_edits.items():
                memo_data[key] = val

        st.success("✅ Memo generated successfully!")

        with open(file_path, "rb") as f:
            memo_bytes = f.read()

        st.download_button(
            label="⬇️ Download Mediation Memo (.docx)",
            data=memo_bytes,
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
                icon = "💥" if "damage" in key.lower() else "📜"
                with st.expander(f"{icon} {label} Quotes Extracted"):
                    for q in value.strip().split("\n\n"):
                        st.markdown(f"- {q.strip()}")

        try:
            log_usage(
                event_type="memo_generated",
                tenant_id=tenant_id,
                user_id=user_id,
                count=1,
                metadata={
                    "court": court,
                    "plaintiffs": valid_plaintiffs,
                    "defendants": valid_defendants,
                    "quote_categories": quote_categories,
                },
            )
        except Exception as log_err:
            logger.warning(redact_log(mask_phi(f"[{ERROR_CODE}] ⚠️ Failed to log memo usage: {log_err}")))

        try:
            log_audit_event("Mediation Memo Generated", {
                "tenant_id": tenant_id,
                "court": court,
                "case_number": case_number,
                "plaintiffs": valid_plaintiffs,
                "defendants": valid_defendants,
                "module": "mediation",
            })

            template_name = selected_template_name if template_choice == "Use Saved Template" else (
                uploaded_template.name if uploaded_template else "Unknown"
            )

            log_audit_event("Mediation Template Used", {
                "template": template_name,
                "example_used": selected_example_name if example_text else "None",
                "tenant_id": tenant_id,
                "module": "mediation"
            })

        except Exception as audit_err:
            logger.warning(redact_log(mask_phi(f"[{ERROR_CODE}] ⚠️ Failed to write audit log: {audit_err}")))

    except Exception as outer_e:
        msg = handle_error(outer_e, code="MEMO_UI_001")
        st.error(msg)
