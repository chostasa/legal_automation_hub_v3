import dropbox
import pandas as pd
from io import BytesIO
import asyncio
import time

from config import AppConfig, get_config
from logger import logger
from utils.retry_utils import http_retry
from core.security import mask_phi, redact_log
from core.error_handling import handle_error
from core.auth import get_tenant_id, get_user_id, enforce_quota
from core.db import insert_audit_event


class DropboxClient:
    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()
        try:
            self.dbx = dropbox.Dropbox(
                app_key=self.config.DROPBOX_APP_KEY,
                app_secret=self.config.DROPBOX_APP_SECRET,
                oauth2_refresh_token=self.config.DROPBOX_REFRESH_TOKEN,
            )
        except Exception as e:
            handle_error(e, code="DROPBOX_INIT_001", raise_it=True)

    @http_retry
    async def download_dashboard_df(
        self, file_path: str = None, sheet_name: str = "Master Dashboard"
    ) -> pd.DataFrame:
        """
        Downloads the dashboard Excel from Dropbox and returns it as a DataFrame.
        Includes retries, audit logging, robust error handling, quota enforcement, and metrics logging.
        """
        path = file_path or self.config.DROPBOX_MASTER_DASHBOARD_PATH
        tenant_id = get_tenant_id()
        user_id = get_user_id()

        try:
            enforce_quota(tenant_id, "dropbox_download")
            start_time = time.perf_counter()

            loop = asyncio.get_event_loop()
            metadata, res = await loop.run_in_executor(None, self.dbx.files_download, path)
            if not res or not res.content:
                raise ValueError(f"No content returned from Dropbox for path: {path}")

            duration = time.perf_counter() - start_time
            logger.info(
                f"[DROPBOX_DOWNLOAD_000] 📥 Successfully downloaded file from Dropbox: {mask_phi(path)} "
                f"(duration={duration:.2f}s, size={len(res.content)} bytes)"
            )

            insert_audit_event(
                tenant_id=tenant_id,
                user_id=user_id,
                action="Dropbox Dashboard Downloaded",
                metadata={"path": path, "duration": f"{duration:.2f}s", "size": len(res.content)},
            )

            try:
                df = pd.read_excel(BytesIO(res.content), sheet_name=sheet_name)
                if df.empty:
                    raise ValueError(f"Downloaded Excel is empty for path: {path}")
                return df
            except Exception as parse_err:
                handle_error(parse_err, code="DROPBOX_PARSE_001", raise_it=True)

        except Exception as e:
            logger.error(redact_log(mask_phi(f"[DROPBOX_DOWNLOAD_001] ❌ Error downloading file {path}: {e}")))
            handle_error(e, code="DROPBOX_DOWNLOAD_001", raise_it=True)

    async def test_connection(self) -> bool:
        """
        Verifies that the Dropbox connection is valid for testing purposes.
        Returns True if the account info can be retrieved, False otherwise.
        """
        tenant_id = get_tenant_id()
        user_id = get_user_id()

        try:
            start_time = time.perf_counter()
            loop = asyncio.get_event_loop()
            account_info = await loop.run_in_executor(None, self.dbx.users_get_current_account)
            duration = time.perf_counter() - start_time

            logger.info(
                f"[DROPBOX_TEST_000] ✅ Dropbox connection valid for user: {mask_phi(account_info.email)} "
                f"(duration={duration:.2f}s)"
            )

            insert_audit_event(
                tenant_id=tenant_id,
                user_id=user_id,
                action="Dropbox Connection Test",
                metadata={"email": account_info.email, "duration": f"{duration:.2f}s"},
            )

            return True
        except Exception as e:
            logger.error(redact_log(mask_phi(f"[DROPBOX_TEST_001] ❌ Error testing connection: {e}")))
            handle_error(e, code="DROPBOX_TEST_001")
            return False


@http_retry
async def download_dashboard_df(file_path: str = None, sheet_name: str = "Master Dashboard") -> pd.DataFrame:
    """
    Standalone helper for downloading the dashboard Excel from Dropbox.
    Includes audit logging for tenant/user context, quota enforcement, and metrics logging.
    """
    try:
        start_time = time.perf_counter()
        client = DropboxClient()
        df = await client.download_dashboard_df(file_path=file_path, sheet_name=sheet_name)
        duration = time.perf_counter() - start_time
        logger.info(f"[DROPBOX_DOWNLOAD_002] ⏱️ Total duration for dashboard download: {duration:.2f}s")
        return df
    except Exception as e:
        logger.error(redact_log(mask_phi(f"[DROPBOX_DOWNLOAD_002] ❌ Error downloading dashboard: {e}")))
        handle_error(e, code="DROPBOX_DOWNLOAD_002", raise_it=True)
