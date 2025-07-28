import streamlit as st
import pandas as pd
import os
import asyncio
from datetime import datetime

from services.email_service import build_email, send_email_and_update
from services.dropbox_client import download_dashboard_df, download_template_file
from core.security import redact_log, mask_phi
from core.usage_tracker import log_usage, check_quota, get_usage_summary
from core.auth import get_user_id, get_tenant_id, get_tenant_branding
from core.audit import log_audit_event
from core.error_handling import handle_error, AppError
from logger import logger
from utils.file_utils import clean_temp_dir
from core.db import get_templates

clean_temp_dir()

# Column names for client details in dashboard data
NAME_COLUMN = "Case Details First Party Name (Full - Last, First)"
EMAIL_COLUMN = "Case Details First Party Details Default Email Account Address"


def run_ui():
    tenant_id = get_tenant_id()
    branding = get_tenant_branding(tenant_id)

    st.header(f"📧 Welcome Email Sender – {branding.get('firm_name', tenant_id)}")

    # Load dashboard data
    try:
        with st.spinner("📥 Loading dashboard data..."):
            df = download_dashboard_df().copy()
    except Exception as e:
        msg = handle_error(e, code="EMAIL_UI_001")
        st.error(msg)
        return

    # Check required columns exist
    if NAME_COLUMN not in df.columns or EMAIL_COLUMN not in df.columns:
        st.error(
            f"❌ Expected columns '{NAME_COLUMN}' and '{EMAIL_COLUMN}' not found in dashboard data."
        )
        return

    # Load templates from DB
    email_templates = get_templates(tenant_id=tenant_id, category="email")
    if not email_templates:
        st.warning("⚠️ No email templates found. Please upload one in Template Manager.")
        return

    # Template selection
    template_options = [t["name"] for t in email_templates]
    selected_template_name = st.selectbox("Select Email Template", template_options)

    if not selected_template_name:
        st.error("❌ Selected template not found.")
        return

    # Download the template from Dropbox locally
    try:
        template_path = download_template_file("email", selected_template_name)

        # Final safety check for unexpected issues
        template_path = os.path.normpath(template_path)
        if "templates/templates" in template_path:
            template_path = template_path.replace("templates/templates", "templates")
        if template_path.endswith(".txt.txt"):
            template_path = template_path.replace(".txt.txt", ".txt")

        if not os.path.exists(template_path):
            st.error(f"❌ Template file not found locally: {template_path}")
            return
    except Exception as e:
        msg = handle_error(e, code="EMAIL_UI_005")
        st.error(f"❌ Failed to download template: {msg}")
        return

    # Sidebar filters
    with st.sidebar:
        st.markdown("### 🔎 Filter Clients")
        class_codes = sorted(df["Class Code Title"].dropna().unique())
        statuses = sorted(df["Status"].dropna().unique()) if "Status" in df.columns else []

        selected_codes = st.multiselect("Class Code", class_codes, default=class_codes)
        selected_statuses = st.multiselect("Status", statuses, default=statuses) if statuses else []

        st.markdown("### 📊 Usage Summary")
        try:
            usage_summary = get_usage_summary(tenant_id, get_user_id())
            st.write(f"📨 Emails Sent: {usage_summary.get('emails_sent', 0)}")
            st.write(f"🧠 OpenAI Tokens Used: {usage_summary.get('openai_tokens', 0)}")
        except Exception:
            st.write("⚠️ Unable to load usage summary.")

    # Filter the dataframe based on filters
    filtered_df = df[
        df["Class Code Title"].isin(selected_codes)
        & (df["Status"].isin(selected_statuses) if statuses else True)
    ]

    # Search bar
    search = st.text_input("🔍 Search client name or email").strip().lower()
    if search:
        filtered_df = filtered_df[
            filtered_df[NAME_COLUMN].str.lower().str.contains(search)
            | filtered_df[EMAIL_COLUMN].str.lower().str.contains(search)
        ]

    # Multi-select client list
    selected_clients = st.multiselect(
        "Select Clients to Email", filtered_df[NAME_COLUMN].tolist()
    )

    # Initialize session state for previews and statuses
    if "email_previews" not in st.session_state:
        st.session_state.email_previews = []
    if "email_status" not in st.session_state:
        st.session_state.email_status = {}

    # ==================== Preview Emails ==================== #
    if st.button("🔍 Preview Emails"):
        st.session_state.email_previews = []
        st.session_state.email_status = {}

        for i, (_, row) in enumerate(
            filtered_df[filtered_df[NAME_COLUMN].isin(selected_clients)].iterrows()
        ):
            try:
                # Prepare row data
                row_data = row.to_dict()
                row_data["Client Name"] = row_data.get(NAME_COLUMN, "")
                row_data["Email"] = row_data.get(EMAIL_COLUMN, "")

                if not row_data["Email"]:
                    st.warning(f"⚠️ Skipping {row_data['Client Name']} - missing email.")
                    continue

                # Build email using template_path
                subject, body, cc, client = asyncio.run(build_email(row_data, template_path))

                subject_key = f"subject_{i}"
                body_key = f"body_{i}"
                status_key = f"status_{i}"

                st.markdown(f"**{client['ClientName']}** — _{client['Email']}_")
                st.text_input("✏️ Subject", subject, key=subject_key)
                st.text_area("📄 Body", body, key=body_key, height=300)
                st.markdown(
                    f"**Status**: {st.session_state.email_status.get(status_key, '⏳ Ready')}"
                )

                if st.button(f"📧 Send to {client['ClientName']}", key=f"send_{i}"):
                    try:
                        check_quota(tenant_id, get_user_id(), "emails_sent", 1)
                        with st.spinner(f"📧 Sending email to {client['ClientName']}..."):
                            status = asyncio.run(
                                send_email_and_update(client, subject, body, cc, template_path)
                            )
                            st.session_state.email_status[status_key] = status

                            log_usage(
                                "emails_sent",
                                tenant_id,
                                get_user_id(),
                                1,
                                {"template_path": template_path},
                            )
                            log_audit_event(
                                "Email Sent",
                                {
                                    "client_name": client["ClientName"],
                                    "template_path": template_path,
                                    "tenant_id": tenant_id,
                                },
                            )
                    except Exception as send_err:
                        err_msg = handle_error(send_err, code="EMAIL_UI_002")
                        st.session_state.email_status[status_key] = err_msg

                st.session_state.email_previews.append(
                    {
                        "client": client,
                        "subject_key": subject_key,
                        "body_key": body_key,
                        "cc": cc,
                        "status_key": status_key,
                    }
                )

            except Exception as e:
                msg = handle_error(e, code="EMAIL_UI_003")
                st.error(
                    f"❌ Error building email for {row.get(NAME_COLUMN, 'Unknown')}: {msg}"
                )

    # ==================== Send All ==================== #
    if st.session_state.email_previews and st.button("📤 Send All"):
        with st.spinner("📤 Sending all emails..."):

            async def send_all():
                tasks = []
                for preview in st.session_state.email_previews:
                    # Skip already-sent emails
                    if "✅" in st.session_state.email_status.get(preview["status_key"], ""):
                        continue

                    client = preview["client"]
                    subject = st.session_state.get(preview["subject_key"], "")
                    body = st.session_state.get(preview["body_key"], "")
                    cc = preview["cc"]

                    async def send_one(preview_item, client_data, subj, bod, cc_list):
                        try:
                            check_quota(tenant_id, get_user_id(), "emails_sent", 1)
                            status = await send_email_and_update(
                                client_data, subj, bod, cc_list, template_path
                            )
                            st.session_state.email_status[preview_item["status_key"]] = status

                            log_usage(
                                "emails_sent",
                                tenant_id,
                                get_user_id(),
                                1,
                                {"template_path": template_path},
                            )
                            log_audit_event(
                                "Batch Email Sent",
                                {
                                    "client_name": client_data["ClientName"],
                                    "template_path": template_path,
                                    "tenant_id": tenant_id,
                                },
                            )
                        except Exception as e:
                            err_msg = handle_error(e, code="EMAIL_UI_004")
                            st.session_state.email_status[preview_item["status_key"]] = err_msg

                    tasks.append(send_one(preview, client, subject, body, cc))

                if tasks:
                    await asyncio.gather(*tasks)

            asyncio.run(send_all())

    # ==================== Export Logs ==================== #
    log_dir = os.path.join("email_automation", "logs")
    csv_path = os.path.join(log_dir, f"{tenant_id}_sent_email_log.csv")
    json_path = os.path.join(log_dir, f"{tenant_id}_sent_email_log.json")

    st.markdown("### 📂 Email Log Export")
    if os.path.exists(csv_path):
        with open(csv_path, "rb") as f:
            st.download_button(
                "⬇️ Download Email Log (CSV)", f, file_name=os.path.basename(csv_path)
            )
    if os.path.exists(json_path):
        with open(json_path, "rb") as f:
            st.download_button(
                "⬇️ Download Email Log (JSON)", f, file_name=os.path.basename(json_path)
            )
