import aiohttp
import asyncio
import time
from config import AppConfig, get_config
from utils.retry_utils import http_retry
from core.security import redact_log, mask_phi
from core.error_handling import handle_error, AppError
from core.usage_tracker import enforce_quota, record_latency_metric
from core.auth import get_tenant_id
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
    async def get_case(self, case_id: str) -> dict:
        try:
            if not case_id or not isinstance(case_id, str):
                raise AppError(
                    code="NEOS_GET_000",
                    message=f"Invalid case_id provided: {case_id}"
                )
            await enforce_quota(get_tenant_id(), "neos_requests")
            url = f"{self.base_url}/cases/{case_id}"
            start_time = time.perf_counter()
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, timeout=10) as response:
                    latency = time.perf_counter() - start_time
                    record_latency_metric("neos_get_case_latency", latency)
                    if response.status != 200:
                        raise AppError(code="NEOS_GET_001", message=f"NEOS GET failed: {response.status}")
                    data = await response.json()
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
    async def update_case_status(self, case_id: str, class_code_title: str) -> None:
        try:
            if not case_id or not class_code_title:
                raise AppError(
                    code="NEOS_UPDATE_000",
                    message=f"Invalid input for update_case_status: case_id={case_id}, class_code_title={class_code_title}"
                )
            await enforce_quota(get_tenant_id(), "neos_requests")
            url = f"{self.base_url}/cases/{case_id}/class-code"
            payload = {"classCodeTitle": class_code_title}
            start_time = time.perf_counter()
            async with aiohttp.ClientSession() as session:
                async with session.put(url, headers=self.headers, json=payload, timeout=10) as response:
                    latency = time.perf_counter() - start_time
                    record_latency_metric("neos_update_case_latency", latency)
                    if response.status != 200:
                        raise AppError(code="NEOS_UPDATE_002", message=f"NEOS UPDATE failed: {response.status}")
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
    async def upload_document(self, case_id: str, filename: str, file_bytes: bytes) -> None:
        try:
            if not case_id or not filename or not file_bytes:
                raise AppError(
                    code="NEOS_UPLOAD_000",
                    message=f"Invalid input for upload_document: case_id={case_id}, filename={filename}"
                )
            await enforce_quota(get_tenant_id(), "neos_requests")
            url = f"{self.base_url}/cases/{case_id}/documents"
            headers = {
                "Authorization": f"Bearer {self.token}"
            }
            data = aiohttp.FormData()
            data.add_field("file", file_bytes, filename=filename)
            start_time = time.perf_counter()
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data, timeout=20) as response:
                    latency = time.perf_counter() - start_time
                    record_latency_metric("neos_upload_document_latency", latency)
                    if response.status != 200:
                        raise AppError(code="NEOS_UPLOAD_003", message=f"NEOS UPLOAD failed: {response.status}")
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
