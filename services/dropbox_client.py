import dropbox
import pandas as pd
from io import BytesIO
from config import AppConfig, get_config
from core.error_handling import handle_error
from logger import logger

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

    def download_dashboard_df(self, file_path: str = None, sheet_name: str = "Master Dashboard") -> pd.DataFrame:
        """
        Synchronous version: Download the dashboard Excel from Dropbox and return as DataFrame.
        """
        path = file_path or self.config.DROPBOX_MASTER_DASHBOARD_PATH

        try:
            metadata, res = self.dbx.files_download(path)
            if not res or not res.content:
                raise ValueError(f"No content returned from Dropbox for path: {path}")

            df = pd.read_excel(BytesIO(res.content), sheet_name=sheet_name)
            if df.empty:
                raise ValueError(f"Downloaded Excel is empty for path: {path}")

            logger.info(f"[DROPBOX_DOWNLOAD] 📥 Downloaded dashboard from {path} ({len(df)} rows)")
            return df

        except Exception as e:
            handle_error(e, code="DROPBOX_DOWNLOAD_001", raise_it=True)
