import re
import html

SAFE_FILENAME_CHARS = r"[^a-zA-Z0-9_\-\.]"
SAFE_TEXT_CHARS = r"[^a-zA-Z0-9\s,\.\-_'\"\(\)\[\]@:]"

def sanitize_filename(value: str) -> str:
    value = re.sub(SAFE_FILENAME_CHARS, "_", value)
    return value.strip("_")

def sanitize_email(email: str) -> str:
    email = email.strip()
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return "invalid@example.com"
    return email

def sanitize_text(text: str) -> str:
    text = html.escape(text)
    return re.sub(SAFE_TEXT_CHARS, "", text).strip()

def redact_log(text: str) -> str:
    return re.sub(r"(api|key|token|secret)[^\s\"']+", "***REDACTED***", text, flags=re.IGNORECASE)
