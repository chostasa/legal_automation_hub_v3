import pytest
from services import email_service

def test_send_email_invalid_inputs():
    with pytest.raises(Exception):
        email_service.send_email(
            sender="", recipients=[], subject="", body=""
        )
