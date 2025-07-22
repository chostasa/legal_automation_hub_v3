# services/email_service.py

import os
import pandas as pd
from datetime import datetime
from core.security import sanitize_text, sanitize_email, redact_log
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
    Returns (subject, body, cc, sanitized_dict) for a given client row.
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
    Sends the email, updates NEOS, logs usage and returns a result string.
    """
    try:
        graph.send_email(sender_address=None, to=client["Email"], subject=subject, body=body)
        neos.update_case_status(client["CaseID"], STATUS_QUESTIONNAIRE_SENT)
        log_email(client, subject, body, template_key, cc)
        log_usage("emails_sent", get_tenant_id(), get_user_id(), 1, {"template": template_key})
        return "✅ Sent"
    except Exception as e:
        fallback_name = client.get("ClientName", "[Unknown Client]")
        logger.error(redact_log(f"❌ Failed to send email to {fallback_name}: {e}"))
        return f"❌ Failed: {type(e).__name__}"


def log_email(client: dict, subject: str, body: str, template_key: str, cc: list):
    """
    Appends the sent email metadata to a CSV log file.
    """
    try:
        subject_clean = sanitize_text(subject)
        body_clean = sanitize_text(body)
        email_clean = sanitize_email(client.get("Email", "invalid@example.com"))
        name_clean = sanitize_text(client.get("ClientName", "Unknown"))

        log_path = os.path.join("email_automation", "logs", "sent_email_log.csv")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        entry = {
            "Timestamp": datetime.now().isoformat(),
            "Client Name": name_clean,
            "Email": email_clean,
            "Subject": subject_clean,
            "Body": body_clean,
            "Template": template_key,
            "CC List": ", ".join(cc),
            "Case ID": client.get("CaseID", ""),
            "Class Code Before": STATUS_INTAKE_COMPLETED,
            "Class Code After": STATUS_QUESTIONNAIRE_SENT,
            "User ID": get_user_id(),
            "Tenant ID": get_tenant_id()
        }

        if os.path.exists(log_path):
            existing = pd.read_csv(log_path)
            pd.concat([existing, pd.DataFrame([entry])], ignore_index=True).to_csv(log_path, index=False)
        else:
            pd.DataFrame([entry]).to_csv(log_path, index=False)

    except Exception as e:
        logger.error(redact_log(f"❌ Failed to log email for {client.get('ClientName', 'Unknown')}: {e}"))
