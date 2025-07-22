import dropbox
import pandas as pd
from io import BytesIO

from config import AppConfig, get_config
from logger import logger
from utils.retry_utils import http_retry


class DropboxClient:
    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()
        try:
            self.dbx = dropbox.Dropbox(
                app_key=self.config.DROPBOX_APP_KEY,
                app_secret=self.config.DROPBOX_APP_SECRET,
                oauth2_refresh_token=self.config.DROPBOX_REFRESH_TOKEN
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize Dropbox client: {e}")
            raise

    @http_retry
    def download_dashboard_df(self, file_path: str = None, sheet_name: str = "Master Dashboard") -> pd.DataFrame:
        path = file_path or self.config.DROPBOX_MASTER_DASHBOARD_PATH
        try:
            metadata, res = self.dbx.files_download(path)
            content = res.content
            logger.info(f"📥 Downloaded {path} from Dropbox")
            return pd.read_excel(BytesIO(content), sheet_name=sheet_name)
        except Exception as e:
            logger.error(f"❌ Failed to download or parse {path}: {e}")
            raise RuntimeError("Dropbox download failed")


# 🔁 Optional standalone method for UI modules that expect a global import
@http_retry
def download_dashboard_df(file_path: str = None, sheet_name: str = "Master Dashboard") -> pd.DataFrame:
    """
    Downloads the dashboard Excel from Dropbox and returns it as a DataFrame.
    Meant to be imported directly into UI modules.
    """
    client = DropboxClient()
    return client.download_dashboard_df(file_path=file_path, sheet_name=sheet_name)
