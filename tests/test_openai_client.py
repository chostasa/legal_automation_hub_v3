from services.openai_client import safe_generate
from unittest.mock import patch, MagicMock

@patch("services.openai_client.client.chat.completions.create")
def test_safe_generate_returns_string(mock_create):
    mock_message = MagicMock()
    mock_message.content = "Negligence is the failure to exercise reasonable care."

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_create.return_value = MagicMock(choices=[mock_choice])

    output = safe_generate("What is negligence?")
    assert isinstance(output, str)
    assert "Negligence" in output
