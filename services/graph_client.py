import requests
from config import AppConfig, get_config
from utils.retry_utils import http_retry
from core.security import redact_log, mask_phi
from core.error_handling import handle_error
from logger import logger

GRAPH_TOKEN_ENDPOINT = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class GraphClient:
    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()
        self.token = self._get_token()

    @http_retry
    def _get_token(self) -> str:
        """
        Retrieve Microsoft Graph API access token with retry and error handling.
        """
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
                handle_error(
                    ValueError("No access token returned from Microsoft."),
                    code="GRAPH_AUTH_002",
                    user_message="Unable to authenticate with Microsoft Graph. Please contact support.",
                    raise_it=True
                )

            return token

        except Exception as e:
            handle_error(
                e,
                code="GRAPH_AUTH_001",
                user_message="Failed to authenticate with Microsoft Graph.",
                raise_it=True
            )

    @http_retry
    def send_email(self, sender_address: str, to: str, subject: str, body: str):
        """
        Send an email using Microsoft Graph API with retry and error handling.
        """
        try:
            if not sender_address or not to or not subject or not body:
                handle_error(
                    ValueError("One or more required email fields are empty."),
                    code="GRAPH_SEND_003",
                    user_message="Cannot send email because required fields are missing.",
                    raise_it=True
                )

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
                "saveToSentItems": "true"
            }

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()

            logger.info(mask_phi(redact_log(f"✅ Email sent via Graph to {to}")))
            return True

        except requests.exceptions.HTTPError as http_err:
            handle_error(
                http_err,
                code="GRAPH_SEND_001",
                user_message=f"Failed to send email to {to}.",
                raise_it=True
            )
        except Exception as e:
            handle_error(
                e,
                code="GRAPH_SEND_002",
                user_message=f"Graph email send failed for {to}.",
                raise_it=True
            )
