import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime

from core.constants import STATUS_INTAKE_COMPLETED, STATUS_QUESTIONNAIRE_SENT
from core.session import get_secure_temp_dir
from core.security import sanitize_email, sanitize_text, redact_log
from core.auth import get_user_id, get_tenant_id
from core.usage_tracker import log_usage

from services.graph_client import GraphClient
from services.neos_client import NeosClient
from services.dropbox_client import download_dashboard_df
from email_automation.utils.template_engine import merge_template
from logger import logger


def run_ui():
    st.header("📧 Welcome Email Sender")

    try:
        df = download_dashboard_df()
        df = df[df["Class Code Title"] == STATUS_INTAKE_COMPLETED].copy()
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to load dashboard data: {e}"))
        st.error("❌ Failed to load dashboard data.")
        return

    graph = GraphClient()
    neos = NeosClient()

    template_dir = "email_automation/templates"
    template_files = glob.glob(os.path.join(template_dir, "*.txt"))
    template_keys = [os.path.splitext(os.path.basename(f))[0] for f in template_files]
    template_key = st.selectbox("Select Email Template", template_keys)

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

    if "email_previews" not in st.session_state:
        st.session_state.email_previews = []
    if "email_status" not in st.session_state:
        st.session_state.email_status = {}

    if st.button("🔍 Preview Emails"):
        st.session_state.email_previews = []
        st.session_state.email_status = {}

        for i, (_, row) in enumerate(filtered_df[filtered_df["Client Name"].isin(selected_clients)].iterrows()):
            try:
                client = {
                    "ClientName": row["Client Name"],
                    "ReferringAttorney": row.get("Referring Attorney", "N/A"),
                    "ReferringAttorneyEmail": row.get("Referring Attorney Email", ""),
                    "CaseID": row.get("Case ID", ""),
                    "Email": sanitize_email(row["Email"])
                }

                subject, body, cc = merge_template(template_key, client)
                subject_key = f"subject_{i}"
                body_key = f"body_{i}"
                status_key = f"status_{i}"

                st.markdown(f"**{client['ClientName']}** — _{client['Email']}_")
                st.text_input("✏️ Subject", subject, key=subject_key)
                st.text_area("📄 Body", body, key=body_key, height=300)
                st.markdown(f"**Status**: {st.session_state.email_status.get(status_key, '⏳ Ready')}")

                if st.button(f"📧 Send to {client['ClientName']}", key=f"send_{i}"):
                    try:
                        graph.send_email(sender_address=None, to=client["Email"], subject=subject, body=body)
                        neos.update_case_status(client["CaseID"], STATUS_QUESTIONNAIRE_SENT)
                        st.session_state.email_status[status_key] = "✅ Sent"
                        log_email(client, subject, body, template_key, cc)
                        log_usage("emails_sent", get_tenant_id(), get_user_id(), 1, {"template": template_key})
                    except Exception as send_err:
                        st.session_state.email_status[status_key] = f"❌ Failed: {send_err}"
                        logger.error(redact_log(f"❌ Email send failed for {client['ClientName']}: {send_err}"))

                st.session_state.email_previews.append({
                    "client": client,
                    "subject_key": subject_key,
                    "body_key": body_key,
                    "cc": cc,
                    "status_key": status_key
                })

            except Exception as e:
                logger.error(redact_log(f"❌ Failed to build email preview for {row.get('Client Name', 'Unknown')}: {e}"))
                st.error(f"❌ Error building email for {row.get('Client Name', 'Unknown')}")

    if st.session_state.email_previews and st.button("📤 Send All"):
        for preview in st.session_state.email_previews:
            if "✅" in st.session_state.email_status.get(preview["status_key"], ""):
                continue

            client = preview["client"]
            subject = st.session_state.get(preview["subject_key"], "")
            body = st.session_state.get(preview["body_key"], "")
            cc = preview["cc"]

            try:
                graph.send_email(sender_address=None, to=client["Email"], subject=subject, body=body)
                neos.update_case_status(client["CaseID"], STATUS_QUESTIONNAIRE_SENT)
                st.session_state.email_status[preview["status_key"]] = "✅ Sent"
                log_email(client, subject, body, template_key, cc)
                log_usage("emails_sent", get_tenant_id(), get_user_id(), 1, {"template": template_key})
            except Exception as e:
                logger.error(redact_log(f"❌ Batch send failed for {client['ClientName']}: {e}"))
                st.session_state.email_status[preview["status_key"]] = f"❌ {e}"


def log_email(client, subject, body, template_key, cc):
    subject = sanitize_text(subject)
    body = sanitize_text(body)
    email = sanitize_email(client["Email"])

    log_path = os.path.join("email_automation", "logs", "sent_email_log.csv")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    entry = {
        "Timestamp": datetime.now().isoformat(),
        "Client Name": client["ClientName"],
        "Email": email,
        "Subject": subject,
        "Body": body,
        "Template": template_key,
        "CC List": ", ".join(cc),
        "Case ID": client["CaseID"],
        "Class Code Before": STATUS_INTAKE_COMPLETED,
        "Class Code After": STATUS_QUESTIONNAIRE_SENT,
        "User ID": get_user_id(),
        "Tenant ID": get_tenant_id()
    }

    try:
        if os.path.exists(log_path):
            existing = pd.read_csv(log_path)
            pd.concat([existing, pd.DataFrame([entry])], ignore_index=True).to_csv(log_path, index=False)
        else:
            pd.DataFrame([entry]).to_csv(log_path, index=False)
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to log sent email: {e}"))
