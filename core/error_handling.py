import traceback
from datetime import datetime
from core.security import mask_phi, redact_log
from core.auth import get_tenant_id, get_user_id
from logger import logger

class AppError(Exception):
    """
    Standardized application error that carries a code and user-facing message.
    """
    def __init__(self, code: str, message: str, details: str = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or ""

    def __str__(self):
        return f"[{self.code}] {self.message}"


def handle_error(e: Exception, code: str = "GENERIC_000", user_message: str = None, raise_it: bool = False):
    """
    Centralized error handler.
    - Logs detailed stack trace and context (tenant, user).
    - Returns a user-facing message with error code for UI display.
    - Optionally raises an AppError for upstream handling.

    Args:
        e (Exception): Original exception
        code (str): Unique error code (e.g., FOIA_GEN_001)
        user_message (str): Friendly message shown to user
        raise_it (bool): Raise AppError instead of returning string
    """
    tenant_id = get_tenant_id() or "UNKNOWN_TENANT"
    user_id = get_user_id() or "UNKNOWN_USER"

    # Mask sensitive info before logging
    error_str = mask_phi(redact_log(str(e)))
    tb_str = mask_phi(redact_log(traceback.format_exc()))

    # Detailed log entry
    logger.error(
        f"[{code}] ❌ Error for tenant={tenant_id}, user={user_id}\n"
        f"→ Exception: {error_str}\n"
        f"→ Traceback: {tb_str}"
    )

    # Friendly message to surface to user
    user_friendly = user_message or "An unexpected error occurred. Please contact support."
    user_friendly = f"❌ {user_friendly} (Error Code: {code})"

    if raise_it:
        # Raise standardized AppError with context
        raise AppError(code=code, message=user_friendly, details=error_str)

    return user_friendly


def log_warning(msg: str, code: str = "GENERIC_WARN", context: dict = None):
    """
    Centralized warning logger with tenant/user context.
    """
    tenant_id = get_tenant_id() or "UNKNOWN_TENANT"
    user_id = get_user_id() or "UNKNOWN_USER"
    ctx = f" ctx={context}" if context else ""

    logger.warning(f"[{code}] ⚠️ Warning for tenant={tenant_id}, user={user_id}{ctx}: {mask_phi(redact_log(msg))}")


def log_info(msg: str, code: str = "GENERIC_INFO", context: dict = None):
    """
    Centralized info logger with tenant/user context.
    """
    tenant_id = get_tenant_id() or "UNKNOWN_TENANT"
    user_id = get_user_id() or "UNKNOWN_USER"
    ctx = f" ctx={context}" if context else ""

    logger.info(f"[{code}] ℹ️ Info for tenant={tenant_id}, user={user_id}{ctx}: {mask_phi(redact_log(msg))}")
