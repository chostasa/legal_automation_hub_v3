import os
import shutil
import time
from core.security import mask_phi, redact_log
from core.error_handling import handle_error
from core.db import soft_delete_template  # Phase 6 DB integration for soft deletes
from logger import logger

# Maximum allowed file size in bytes (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


def clean_temp_dir(base_dir: str = "temp", expire_minutes: int = 60):
    """
    Deletes all subfolders in `temp/` older than `expire_minutes`.
    If the base_dir doesn't exist, it will be created.
    """
    try:
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
            return

        cutoff = time.time() - (expire_minutes * 60)

        for session_folder in os.listdir(base_dir):
            session_path = os.path.join(base_dir, session_folder)
            if not os.path.isdir(session_path):
                continue

            try:
                last_modified = os.path.getmtime(session_path)
                if last_modified < cutoff:
                    shutil.rmtree(session_path)
            except Exception as folder_err:
                logger.warning(
                    redact_log(mask_phi(f"⚠️ Failed to process folder {session_path}: {folder_err}"))
                )

    except Exception as e:
        handle_error(e, code="FILE_UTILS_CLEAN_001")
        logger.error(
            redact_log(mask_phi(f"❌ Failed to clean temp directory: {e}"))
        )


def remove_file_safe(path: str, template_id: int = None, tenant_id: str = None):
    """
    Safely deletes a file if it exists. If template_id and tenant_id are provided,
    mark the template as soft deleted in the database.
    """
    try:
        if os.path.isfile(path):
            os.remove(path)
            logger.info(redact_log(mask_phi(f"🗑️ File removed: {path}")))
            # Soft delete DB record if applicable
            if template_id and tenant_id:
                soft_delete_template(template_id=template_id, tenant_id=tenant_id)
                logger.info(redact_log(mask_phi(f"🗑️ Marked template {template_id} as deleted in DB")))
    except Exception as e:
        handle_error(e, code="FILE_UTILS_REMOVE_001")
        logger.error(
            redact_log(mask_phi(f"❌ Failed to remove file {path}: {e}"))
        )


def validate_file_size(file_path: str):
    """
    Validate the file size is within the allowed limit.
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            raise ValueError(
                f"File {file_path} exceeds maximum allowed size of {MAX_FILE_SIZE / (1024 * 1024)} MB."
            )

    except Exception as e:
        handle_error(e, code="FILE_UTILS_SIZE_001", raise_it=True)
