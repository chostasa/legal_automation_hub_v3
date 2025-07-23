# utils/file_utils.py

import os
import shutil
import time
from datetime import datetime
from core.session import get_secure_temp_dir
from logger import logger


def clean_temp_dir(base_dir: str = "temp", expire_minutes: int = 60):
    """
    Deletes all subfolders in `temp/` older than `expire_minutes`.
    If the base_dir doesn't exist, it will be created.
    """
    try:
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
            return  # Nothing to clean yet

        cutoff = time.time() - (expire_minutes * 60)

        for session_folder in os.listdir(base_dir):
            session_path = os.path.join(base_dir, session_folder)
            if not os.path.isdir(session_path):
                continue

            try:
                last_modified = os.path.getmtime(session_path)
                if last_modified < cutoff:
                    shutil.rmtree(session_path)
                    # logger.info(f"🧹 Deleted expired session folder: {session_path}")
            except Exception as folder_err:
                logger.warning(f"⚠️ Failed to process folder {session_path}: {folder_err}")

    except Exception as e:
        logger.error(f"❌ Failed to clean temp directory: {e}")


def remove_file_safe(path: str):
    """
    Safely deletes a file if it exists.
    """
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception as e:
        logger.error(f"❌ Failed to remove file {path}: {e}")
