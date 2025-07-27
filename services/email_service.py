import os
import pandas as pd
from datetime import datetime
from core.security import sanitize_text, sanitize_email, redact_log, mask_phi
from core.constants import STATUS_INTAKE_COMPLETED, STATUS_QUESTIONNAIRE_SENT
from core.auth import get_user_id, get_tenant_id
from core.usage_tracker import log_usage
from core.error_handling import handle_error, AppError
from core.audit import log_audit_event
from email_automation.utils.template_engine import merge_template
from services.graph_client import GraphClient
from services.neos_client import NeosClient
from logger import logger

graph = GraphClient()
neos = NeosClient()


def build_email(client_data: dict, template_key: str) -> tuple:
    """
    Returns (subject, body, cc, sanitized_dict) for a given client row.
    Validates input fields and applies sanitization.
    """
    try:
        sanitized = {
            "ClientName": sanitize_text(client_data.get("Client Name", "")),
            "ReferringAttorney": sanitize_text(client_data.get("Referring Attorney", "N/A")),
            "ReferringAttorneyEmail": sanitize_email(client_data.get("Referring Attorney Email", "")),
            "CaseID": sanitize_text(client_data.get("Case ID", "")),
            "Email": sanitize_email(client_data.get("Email", "")),
        }

        if not sanitized["Email"] or sanitized["Email"] == "invalid@example.com":
            raise AppError(
                code="EMAIL_BUILD_001",
                message=f"Invalid email for client: {sanitized.get('ClientName', '[Unknown]')}",
                details=f"Row data: {client_data}",
            )

        subject, body, cc = merge_template(template_key, sanitized)
        if not subject or not body:
            raise AppError(
                code="EMAIL_BUILD_002",
                message=f"Template merge failed for template: {template_key}",
                details=f"Sanitized data: {sanitized}",
            )

        # Audit logging for building email
        log_audit_event("Email Built", {
            "tenant_id": get_tenant_id(),
            "user_id": get_user_id(),
            "client_name": sanitized.get("ClientName"),
            "template": template_key,
        })

        return subject, body, cc, sanitized

    except AppError:
        raise
    except Exception as e:
        handle_error(e, code="EMAIL_BUILD_003", user_message="Failed to build email.", raise_it=True)


def send_email_and_update(client: dict, subject: str, body: str, cc: list, template_key: str) -> str:
    """
    Sends the email, updates NEOS, logs usage and returns a result string.
    """
    try:
        if not client.get("Email") or client["Email"] == "invalid@example.com":
            raise AppError(
                code="EMAIL_SEND_001",
                message=f"Cannot send email: invalid email address for client {client.get('ClientName', '[Unknown]')}",
            )

        with logger.contextualize(tenant_id=get_tenant_id(), user_id=get_user_id()):
            graph.send_email(sender_address=None, to=client["Email"], subject=subject, body=body)

        # Update NEOS case status
        neos.update_case_status(client.get("CaseID", ""), STATUS_QUESTIONNAIRE_SENT)

        # Log email event and usage
        log_email(client, subject, body, template_key, cc)
        log_usage("emails_sent", get_tenant_id(), get_user_id(), 1, {"template": template_key})

        # Audit logging for email sent
        log_audit_event("Email Sent", {
            "tenant_id": get_tenant_id(),
            "user_id": get_user_id(),
            "client_name": client.get("ClientName"),
            "template": template_key,
            "case_id": client.get("CaseID", ""),
        })

        return "✅ Sent"

    except AppError as ae:
        logger.error(redact_log(mask_phi(str(ae))))
        return f"❌ Failed: {ae.code}"
    except Exception as e:
        fallback_name = client.get("ClientName", "[Unknown Client]")
        handle_error(
            e,
            code="EMAIL_SEND_002",
            user_message=f"Failed to send email for {fallback_name}.",
        )
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

        tenant_id = get_tenant_id()
        log_path = os.path.join("email_automation", "logs", f"{tenant_id}_sent_email_log.csv")
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
            "Tenant ID": tenant_id,
        }

        if os.path.exists(log_path):
            existing = pd.read_csv(log_path)
            pd.concat([existing, pd.DataFrame([entry])], ignore_index=True).to_csv(log_path, index=False)
        else:
            pd.DataFrame([entry]).to_csv(log_path, index=False)

        # Audit logging for log write
        log_audit_event("Email Logged", {
            "tenant_id": tenant_id,
            "user_id": get_user_id(),
            "client_name": name_clean,
            "template": template_key,
        })

    except Exception as e:
        handle_error(
            e,
            code="EMAIL_LOG_001",
            user_message=f"Failed to log email for {client.get('ClientName', 'Unknown')}",
        )
