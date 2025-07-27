import re
import html
from core.error_handling import handle_error

SAFE_FILENAME_CHARS = r"[^a-zA-Z0-9_\-\.]"
SAFE_TEXT_CHARS = r"[^a-zA-Z0-9\s,\.\-_'\"\(\)\[\]@:]"

def sanitize_filename(value: str) -> str:
    """
    Sanitize a filename by replacing unsafe characters with underscores.
    """
    try:
        if not isinstance(value, str):
            raise ValueError("sanitize_filename expects a string")
        value = re.sub(SAFE_FILENAME_CHARS, "_", value)
        return value.strip("_")
    except Exception as e:
        handle_error(e, code="SECURITY_SANITIZE_FILENAME_ERR")
        return "invalid_filename"

def sanitize_email(email: str) -> str:
    """
    Validate and sanitize email addresses. Return placeholder if invalid.
    """
    try:
        if not isinstance(email, str):
            raise ValueError("sanitize_email expects a string")
        email = email.strip()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return "invalid@example.com"
        return email
    except Exception as e:
        handle_error(e, code="SECURITY_SANITIZE_EMAIL_ERR")
        return "invalid@example.com"

def sanitize_text(text: str) -> str:
    """
    Escape HTML and remove unsafe characters from text fields.
    """
    try:
        if not isinstance(text, str):
            raise ValueError("sanitize_text expects a string")
        text = html.escape(text)
        return re.sub(SAFE_TEXT_CHARS, "", text).strip()
    except Exception as e:
        handle_error(e, code="SECURITY_SANITIZE_TEXT_ERR")
        return ""

def redact_log(text: str) -> str:
    """
    Redact sensitive keywords (api keys, tokens, secrets) from log output.
    """
    try:
        if not isinstance(text, str):
            raise ValueError("redact_log expects a string")
        return re.sub(
            r"(api|key|token|secret)[^\s\"']+", "***REDACTED***", text, flags=re.IGNORECASE
        )
    except Exception as e:
        handle_error(e, code="SECURITY_REDACT_LOG_ERR")
        return "***REDACTED***"

PHI_FIELDS = ["client", "email", "phone", "narrative", "summary"]

def mask_phi(text: str) -> str:
    """
    Redact likely PHI fields (names, emails, etc.) from log text.
    """
    try:
        if not isinstance(text, str):
            raise ValueError("mask_phi expects a string")
        for field in PHI_FIELDS:
            text = re.sub(
                rf"({field}\s*[:=].*?)(?=,|$)", "[REDACTED]", text, flags=re.IGNORECASE
            )
        return text
    except Exception as e:
        handle_error(e, code="SECURITY_MASK_PHI_ERR")
        return "[REDACTED]"
