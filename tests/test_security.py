import pytest
from core.security import sanitize_filename, sanitize_email, sanitize_text, redact_log

def test_sanitize_filename_valid():
    assert security.sanitize_filename("valid-file.txt") == "valid-file.txt"

def test_sanitize_filename_invalid_type():
    assert security.sanitize_filename(1234) == "invalid_filename"

def test_sanitize_email_valid():
    assert security.sanitize_email("test@example.com") == "test@example.com"

def test_sanitize_email_invalid():
    assert security.sanitize_email("invalid") == "invalid@example.com"

def test_sanitize_text_html_escape():
    assert security.sanitize_text("<b>bold</b>") == "bbolddbb"

def test_redact_log_sensitive():
    text = "apiKey=12345"
    result = security.redact_log(text)
    assert "***REDACTED***" in result

def test_mask_phi_fields():
    sample = "client: John Doe, email: test@example.com"
    masked = security.mask_phi(sample)
    assert "[REDACTED]" in masked
