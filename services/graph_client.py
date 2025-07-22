import requests
from config import AppConfig, get_config
from utils.retry_utils import http_retry
from core.security import redact_log
from logger import logger

GRAPH_TOKEN_ENDPOINT = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

class GraphClient:
    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()
        self.token = self._get_token()

    @http_retry
    def _get_token(self) -> str:
        try:
            url = GRAPH_TOKEN_ENDPOINT.format(tenant_id=self.config.GRAPH_TENANT_ID)
            data = {
                "client_id": self.config.GRAPH_CLIENT_ID,
                "client_secret": self.config.GRAPH_CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials"
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            response = requests.post(url, data=data, headers=headers, timeout=10)
            response.raise_for_status()

            json_resp = response.json()
            token = json_resp.get("access_token")
            if not token:
                logger.error("❌ Graph token response missing 'access_token'")
                raise ValueError("No access token returned from Microsoft.")

            return token
        except Exception as e:
            logger.error(redact_log(f"❌ Failed to retrieve Graph access token: {e}"))
            raise RuntimeError("Microsoft Graph authentication failed.")

    @http_retry
    def send_email(self, sender_address: str, to: str, subject: str, body: str):
        try:
            url = f"{GRAPH_API_BASE}/users/{sender_address}/sendMail"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            payload = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "Text",
                        "content": body
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": to}}
                    ]
                },
                "saveToSentItems": "true"  # 🔐 Optional but useful for audit trail
            }

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"✅ Email sent via Graph to {to}")
        except Exception as e:
            logger.error(redact_log(f"❌ Failed to send Graph email to {to}: {e}"))
            raise RuntimeError("Graph email send failed.")
