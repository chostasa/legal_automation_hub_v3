import streamlit as st
import pandas as pd
import os
import glob

from services.email_service import build_email, send_email_and_update
from services.dropbox_client import download_dashboard_df
from core.constants import STATUS_INTAKE_COMPLETED
from core.security import redact_log, mask_phi
from core.usage_tracker import log_usage
from core.auth import get_user_id, get_tenant_id
from core.audit import log_audit_event
from core.error_handling import handle_error
from logger import logger

from utils.file_utils import clean_temp_dir
clean_temp_dir()


def run_ui():
    st.header("📧 Welcome Email Sender")

    # === Load Dashboard Data ===
    try:
        with st.spinner("📥 Loading dashboard data..."):
            df = download_dashboard_df()
            df = df[df["Class Code Title"] == STATUS_INTAKE_COMPLETED].copy()
    except Exception as e:
        msg = handle_error(e, code="EMAIL_UI_001")
        st.error(msg)
        return

    # === Load Templates ===
    tenant_id = get_tenant_id()
    template_dir = os.path.join("email_automation", tenant_id, "templates")
    os.makedirs(template_dir, exist_ok=True)

    template_files = glob.glob(os.path.join(template_dir, "*.txt"))
    if not template_files:
        st.warning("⚠️ No email templates found. Please upload one in Template Manager.")
        return

    template_keys = [os.path.splitext(os.path.basename(f))[0] for f in template_files]
    template_key = st.selectbox("Select Email Template", template_keys)

    # === Filters ===
    with st.sidebar:
        st.markdown("### 🔎 Filter Clients")
        class_codes = sorted(df["Class Code Title"].dropna().unique())
        statuses = sorted(df["Status"].dropna().unique()) if "Status" in df.columns else []
        selected_codes = st.multiselect("Class Code", class_codes, default=class_codes)
        selected_status = st.multiselect("Status", statuses, default=statuses) if statuses else []

    filtered_df = df[
        df["Class Code Title"].isin(selected_codes) &
        (df["Status"].isin(selected_status) if statuses else True)
    ]

    search = st.text_input("🔍 Search client name or email").strip().lower()
    if search:
        filtered_df = filtered_df[
            filtered_df["Client Name"].str.lower().str.contains(search) |
            filtered_df["Email"].str.lower().str.contains(search)
        ]

    selected_clients = st.multiselect("Select Clients to Email", filtered_df["Client Name"].tolist())

    # === Session State ===
    if "email_previews" not in st.session_state:
        st.session_state.email_previews = []
    if "email_status" not in st.session_state:
        st.session_state.email_status = {}

    # === Preview Individual Emails ===
    if st.button("🔍 Preview Emails"):
        st.session_state.email_previews = []
        st.session_state.email_status = {}

        for i, (_, row) in enumerate(filtered_df[filtered_df["Client Name"].isin(selected_clients)].iterrows()):
            try:
                subject, body, cc, client = build_email(row, template_key)
                subject_key = f"subject_{i}"
                body_key = f"body_{i}"
                status_key = f"status_{i}"

                st.markdown(f"**{client['ClientName']}** — _{client['Email']}_")
                st.text_input("✏️ Subject", subject, key=subject_key)
                st.text_area("📄 Body", body, key=body_key, height=300)
                st.markdown(f"**Status**: {st.session_state.email_status.get(status_key, '⏳ Ready')}")

                if st.button(f"📧 Send to {client['ClientName']}", key=f"send_{i}"):
                    try:
                        with st.spinner(f"📧 Sending email to {client['ClientName']}..."):
                            status = send_email_and_update(client, subject, body, cc, template_key)
                            st.session_state.email_status[status_key] = status

                            # Log usage and audit
                            log_usage("email_sent", tenant_id, get_user_id(), 1, {"template": template_key})
                            log_audit_event("Email Sent", {
                                "client_name": client['ClientName'],
                                "template": template_key,
                                "tenant_id": tenant_id
                            })

                    except Exception as send_err:
                        err_msg = handle_error(send_err, code="EMAIL_UI_002")
                        st.session_state.email_status[status_key] = err_msg

                st.session_state.email_previews.append({
                    "client": client,
                    "subject_key": subject_key,
                    "body_key": body_key,
                    "cc": cc,
                    "status_key": status_key
                })

            except Exception as e:
                msg = handle_error(e, code="EMAIL_UI_003")
                st.error(f"❌ Error building email for {row.get('Client Name', 'Unknown')}: {msg}")

    # === Batch Send ===
    if st.session_state.email_previews and st.button("📤 Send All"):
        with st.spinner("📤 Sending all emails..."):
            for preview in st.session_state.email_previews:
                if "✅" in st.session_state.email_status.get(preview["status_key"], ""):
                    continue

                client = preview["client"]
                subject = st.session_state.get(preview["subject_key"], "")
                body = st.session_state.get(preview["body_key"], "")
                cc = preview["cc"]

                try:
                    status = send_email_and_update(client, subject, body, cc, template_key)
                    st.session_state.email_status[preview["status_key"]] = status

                    # Log usage and audit
                    log_usage("email_sent", tenant_id, get_user_id(), 1, {"template": template_key})
                    log_audit_event("Batch Email Sent", {
                        "client_name": client['ClientName'],
                        "template": template_key,
                        "tenant_id": tenant_id
                    })

                except Exception as e:
                    err_msg = handle_error(e, code="EMAIL_UI_004")
                    st.session_state.email_status[preview["status_key"]] = err_msg
