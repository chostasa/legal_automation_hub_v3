# utils/file_utils.py

import os
import shutil
import time
from datetime import datetime, timedelta
from core.session import get_secure_temp_dir
from logger import logger


def clean_temp_dir(base_dir: str = "temp", expire_minutes: int = 60):
    """
    Deletes all subfolders in `temp/` older than X minutes.
    """
    try:
        cutoff = time.time() - (expire_minutes * 60)
        for session_folder in os.listdir(base_dir):
            session_path = os.path.join(base_dir, session_folder)
            if not os.path.isdir(session_path):
                continue
            if os.path.getmtime(session_path) < cutoff:
                shutil.rmtree(session_path)
    except Exception as e:
        logger.error(f"❌ Failed to clean temp directory: {e}")


def remove_file_safe(path: str):
    """
    Safely delete a file, if it exists.
    """
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.error(f"❌ Failed to remove file {path}: {e}")
