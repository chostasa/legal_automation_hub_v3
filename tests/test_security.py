from core.security import sanitize_filename, sanitize_email, sanitize_text, redact_log

def test_filename():
    assert sanitize_filename("Test/Unsafe\\Name.docx") == "Test_Unsafe_Name.docx"

def test_email():
    assert sanitize_email("bademail") == "invalid@example.com"
    assert sanitize_email("test@example.com") == "test@example.com"

def test_text():
    assert "alert" not in sanitize_text("<script>alert('x')</script>")

def test_redact():
    redacted = redact_log("openai_api_key=abc123XYZ")
    assert "***REDACTED***" in redacted
