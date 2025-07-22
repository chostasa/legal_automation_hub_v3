import requests
from config import AppConfig, get_config
from utils.retry_utils import http_retry
from core.security import redact_log
from logger import logger

class NeosClient:
    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()
        self.base_url = self.config.NEOS_BASE_URL.rstrip("/")
        self.token = self.config.NEOS_API_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    @http_retry
    def get_case(self, case_id: str) -> dict:
        try:
            url = f"{self.base_url}/cases/{case_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(redact_log(f"❌ Failed to get NEOS case {case_id}: {e}"))
            raise RuntimeError("Could not retrieve case from NEOS.")

    @http_retry
    def update_case_status(self, case_id: str, class_code_title: str) -> None:
        try:
            url = f"{self.base_url}/cases/{case_id}/class-code"
            payload = {"classCodeTitle": class_code_title}
            response = requests.put(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"✅ NEOS case {case_id} updated to {class_code_title}")
        except Exception as e:
            logger.error(redact_log(f"❌ Failed to update NEOS case {case_id}: {e}"))
            raise RuntimeError("Failed to update case class code in NEOS.")

    @http_retry
    def upload_document(self, case_id: str, filename: str, file_bytes: bytes) -> None:
        try:
            url = f"{self.base_url}/cases/{case_id}/documents"
            files = {
                "file": (filename, file_bytes),
            }
            response = requests.post(url, headers={"Authorization": f"Bearer {self.token}"}, files=files, timeout=20)
            response.raise_for_status()
            logger.info(f"✅ Document '{filename}' uploaded to NEOS case {case_id}")
        except Exception as e:
            logger.error(redact_log(f"❌ Failed to upload document to NEOS case {case_id}: {e}"))
            raise RuntimeError("Document upload to NEOS failed.")
