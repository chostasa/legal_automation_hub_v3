import pytest
from unittest.mock import patch
from services import openai_client, graph_client, dropbox_client, neos_client

def test_openai_client_safe_generate(monkeypatch):
    client = openai_client.OpenAIClient()
    with patch.object(client.client.chat.completions, "create") as mock_create:
        mock_create.return_value.choices = [type("msg", (), {"message": type("m", (), {"content": "test"})})()]
        result = client.safe_generate(prompt="prompt")
        assert "test" in result

def test_graph_client_auth_failure(monkeypatch):
    with patch("requests.post", side_effect=Exception("Auth error")):
        with pytest.raises(Exception):
            graph_client.GraphClient()._get_token()

def test_dropbox_client_download_invalid(monkeypatch):
    client = dropbox_client.DropboxClient()
    with patch.object(client.dbx, "files_download", side_effect=Exception("download error")):
        with pytest.raises(Exception):
            client.download_dashboard_df()

def test_neos_client_update_case(monkeypatch):
    client = neos_client.NeosClient()
    with patch.object(client, "update_case_status", side_effect=Exception("NEOS error")):
        with pytest.raises(Exception):
            client.update_case_status("case_id", "status")
