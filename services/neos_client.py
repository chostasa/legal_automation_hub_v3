import requests
from config import AppConfig, get_config
from utils.retry_utils import http_retry
from core.security import redact_log, mask_phi
from core.error_handling import handle_error, AppError
from logger import logger


class NeosClient:
    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()
        self.base_url = self.config.NEOS_BASE_URL.rstrip("/")
        self.token = self.config.NEOS_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    @http_retry
    def get_case(self, case_id: str) -> dict:
        """
        Retrieve a case from NEOS.
        """
        try:
            if not case_id or not isinstance(case_id, str):
                raise AppError(
                    code="NEOS_GET_000",
                    message=f"Invalid case_id provided: {case_id}"
                )

            url = f"{self.base_url}/cases/{case_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            if not data or "caseId" not in data:
                raise ValueError(f"Invalid NEOS response: {data}")

            return data

        except Exception as e:
            handle_error(
                e,
                code="NEOS_GET_001",
                user_message=f"Unable to retrieve NEOS case {case_id}.",
                raise_it=True
            )

    @http_retry
    def update_case_status(self, case_id: str, class_code_title: str) -> None:
        """
        Update the class code (status) of a NEOS case.
        """
        try:
            if not case_id or not class_code_title:
                raise AppError(
                    code="NEOS_UPDATE_000",
                    message=f"Invalid input for update_case_status: case_id={case_id}, class_code_title={class_code_title}"
                )

            url = f"{self.base_url}/cases/{case_id}/class-code"
            payload = {"classCodeTitle": class_code_title}

            response = requests.put(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()

            logger.info(
                redact_log(
                    mask_phi(f"✅ NEOS case {case_id} updated to {class_code_title}")
                )
            )

        except Exception as e:
            handle_error(
                e,
                code="NEOS_UPDATE_002",
                user_message=f"Failed to update NEOS case {case_id} to {class_code_title}.",
                raise_it=True
            )

    @http_retry
    def upload_document(self, case_id: str, filename: str, file_bytes: bytes) -> None:
        """
        Upload a document to a NEOS case.
        """
        try:
            if not case_id or not filename or not file_bytes:
                raise AppError(
                    code="NEOS_UPLOAD_000",
                    message=f"Invalid input for upload_document: case_id={case_id}, filename={filename}"
                )

            url = f"{self.base_url}/cases/{case_id}/documents"
            files = {
                "file": (filename, file_bytes),
            }
            headers = {
                "Authorization": f"Bearer {self.token}"
            }

            response = requests.post(url, headers=headers, files=files, timeout=20)
            response.raise_for_status()

            logger.info(
                redact_log(
                    mask_phi(f"✅ Document '{filename}' uploaded to NEOS case {case_id}")
                )
            )

        except Exception as e:
            handle_error(
                e,
                code="NEOS_UPLOAD_003",
                user_message=f"Failed to upload document '{filename}' to NEOS case {case_id}.",
                raise_it=True
            )
