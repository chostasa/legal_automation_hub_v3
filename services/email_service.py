# services/email_service.py

import os
import pandas as pd
from datetime import datetime
from core.security import sanitize_text, sanitize_email
from core.constants import STATUS_INTAKE_COMPLETED, STATUS_QUESTIONNAIRE_SENT
from core.auth import get_user_id, get_tenant_id
from core.usage_tracker import log_usage
from email_automation.utils.template_engine import merge_template
from services.graph_client import GraphClient
from services.neos_client import NeosClient
from logger import logger

graph = GraphClient()
neos = NeosClient()

def build_email(client_data: dict, template_key: str) -> tuple:
    """
    Returns (subject, body, cc) for a given client row.
    """
    sanitized = {
        "ClientName": sanitize_text(client_data.get("Client Name", "")),
        "ReferringAttorney": sanitize_text(client_data.get("Referring Attorney", "N/A")),
        "ReferringAttorneyEmail": client_data.get("Referring Attorney Email", ""),
        "CaseID": client_data.get("Case ID", ""),
        "Email": sanitize_email(client_data.get("Email", ""))
    }

    subject, body, cc = merge_template(template_key, sanitized)
    return subject, body, cc, sanitized


def send_email_and_update(client: dict, subject: str, body: str, cc: list, template_key: str) -> str:
    """
    Sends the email, updates NEOS, logs usage, and returns status string.
    """
    try:
        graph.send_email(sender_address=None, to=client["Email"], subject=subject, body=body)
        neos.update_case_status(client["CaseID"], STATUS_QUESTIONNAIRE_SENT)
        log_email(client, subject, body, template_key, cc)
        log_usage("emails_sent", get_tenant_id(), get_user_id(), 1, {"template": template_key})
        return "✅ Sent"
    except Exception as e:
        logger.error(f"❌ Failed to send email to {client['ClientName']}: {e}")
        return f"❌ Failed: {e}"


def log_email(client: dict, subject: str, body: str, template_key: str, cc: list):
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
        logger.error(f"❌ Failed to log email for {client['ClientName']}: {e}")
