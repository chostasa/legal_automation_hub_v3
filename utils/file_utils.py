# utils/file_utils.py

import os
import shutil
import time
from datetime import datetime, timedelta
from core.session import get_secure_temp_dir
from logger import logger

from utils.file_utils import clean_temp_dir
clean_temp_dir()


def clean_temp_dir(expire_minutes: int = 60):
    """
    Removes all files in the secure session temp directory older than X minutes.
    """
    try:
        temp_dir = get_secure_temp_dir()
        cutoff = time.time() - (expire_minutes * 60)

        for fname in os.listdir(temp_dir):
            fpath = os.path.join(temp_dir, fname)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
            elif os.path.isdir(fpath) and os.path.getmtime(fpath) < cutoff:
                shutil.rmtree(fpath)
    except Exception as e:
        logger.error(f"❌ Failed to clean temp dir: {e}")


def remove_file_safe(path: str):
    """
    Safely delete a file, if it exists.
    """
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.error(f"❌ Failed to remove file {path}: {e}")
