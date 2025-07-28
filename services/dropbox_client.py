import os
import dropbox
import pandas as pd
from io import BytesIO
from config import AppConfig, get_config
from core.error_handling import handle_error
from logger import logger
from core.constants import DROPBOX_TEMPLATES_ROOT, DROPBOX_EXAMPLES_ROOT


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

    def download_dashboard_df(
        self, file_path: str = None, sheet_name: str = "Master Dashboard"
    ) -> pd.DataFrame:
        """Download the dashboard Excel from Dropbox and return as DataFrame."""
        path = file_path or self.config.DROPBOX_MASTER_DASHBOARD_PATH

        try:
            metadata, res = self.dbx.files_download(path)
            if not res or not res.content:
                raise ValueError(f"No content returned from Dropbox for path: {path}")

            df = pd.read_excel(BytesIO(res.content), sheet_name=sheet_name)
            if df.empty:
                raise ValueError(f"Downloaded Excel is empty for path: {path}")

            logger.info(
                f"[DROPBOX_DOWNLOAD] 📥 Downloaded dashboard from {path} ({len(df)} rows)"
            )
            return df

        except Exception as e:
            handle_error(e, code="DROPBOX_DOWNLOAD_001", raise_it=True)

    def list_files(self, folder_path: str):
        """
        List all files in a Dropbox folder. Auto-create folder if it doesn't exist.
        """
        try:
            # Ensure the folder exists (create if missing)
            try:
                self.dbx.files_get_metadata(folder_path)
            except dropbox.exceptions.ApiError as e:
                if (
                    hasattr(e.error, "is_path")
                    and e.error.is_path()
                    and e.error.get_path().is_not_found()
                ):
                    # Folder missing: create it
                    logger.info(f"[DROPBOX] Creating missing folder: {folder_path}")
                    self.dbx.files_create_folder_v2(folder_path)
                else:
                    raise

            result = self.dbx.files_list_folder(folder_path)
            return [entry.name for entry in result.entries if hasattr(entry, "name")]

        except Exception as e:
            handle_error(e, code="DROPBOX_LIST_001", raise_it=True)

    def download_file(self, dropbox_path: str, local_dir: str = "downloads") -> str:
        """Download a file from Dropbox to a local directory and return the local path."""
        try:
            os.makedirs(local_dir, exist_ok=True)
            filename = os.path.basename(dropbox_path)
            local_path = os.path.join(local_dir, filename)

            metadata, res = self.dbx.files_download(dropbox_path)
            with open(local_path, "wb") as f:
                f.write(res.content)

            logger.info(f"[DROPBOX_DOWNLOAD] 📄 Downloaded {dropbox_path} → {local_path}")
            return local_path
        except Exception as e:
            handle_error(e, code="DROPBOX_DOWNLOAD_FILE_001", raise_it=True)

    def ensure_base_folders(self):
        """
        Ensure the full folder tree for templates/examples exists in Dropbox.
        """
        base_folders = [
            f"{DROPBOX_TEMPLATES_ROOT}/email",
            f"{DROPBOX_TEMPLATES_ROOT}/batch_docs",
            f"{DROPBOX_TEMPLATES_ROOT}/foia",
            f"{DROPBOX_TEMPLATES_ROOT}/demand",
            f"{DROPBOX_EXAMPLES_ROOT}/demand",
            f"{DROPBOX_EXAMPLES_ROOT}/foia",
            f"{DROPBOX_EXAMPLES_ROOT}/mediation",
        ]
        for folder in base_folders:
            try:
                self.dbx.files_get_metadata(folder)
            except dropbox.exceptions.ApiError:
                logger.info(f"[DROPBOX] Creating base folder: {folder}")
                self.dbx.files_create_folder_v2(folder)


# === Global helper functions (used by modules) ===

def download_dashboard_df(file_path: str = None, sheet_name: str = "Master Dashboard") -> pd.DataFrame:
    client = DropboxClient()
    return client.download_dashboard_df(file_path=file_path, sheet_name=sheet_name)


def list_templates(category: str):
    """Return list of template files for a category (email, batch_docs, etc.)"""
    client = DropboxClient()
    path = f"{DROPBOX_TEMPLATES_ROOT}/{category}"
    return client.list_files(path)


def download_template_file(category: str, filename: str, local_dir="templates"):
    client = DropboxClient()
    path = f"{DROPBOX_TEMPLATES_ROOT}/{category}/{filename}"
    return client.download_file(path, local_dir)


def list_examples(module: str):
    client = DropboxClient()
    path = f"{DROPBOX_EXAMPLES_ROOT}/{module}"
    return client.list_files(path)


def download_example_file(module: str, filename: str, local_dir="examples"):
    client = DropboxClient()
    path = f"{DROPBOX_EXAMPLES_ROOT}/{module}/{filename}"
    return client.download_file(path, local_dir)
