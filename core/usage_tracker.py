import os
import json
from datetime import datetime
from core.session import get_secure_temp_dir
from core.security import mask_phi, redact_log
from core.error_handling import handle_error
from logger import logger


def get_usage_log_path() -> str:
    """
    Returns the path to the usage log file in the secure temp directory.
    """
    base = get_secure_temp_dir()
    return os.path.join(base, "usage_log.json")


def log_usage(event_type: str, tenant_id: str, user_id: str, amount: int, metadata: dict = None):
    """
    Logs a usage event in JSON format.
    """
    path = get_usage_log_path()
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "amount": amount,
        "metadata": metadata or {},
    }

    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                logs = json.load(f)
        else:
            logs = []

        logs.append(log_entry)

        with open(path, "w") as f:
            json.dump(logs, f, indent=2)

    except Exception as e:
        error_msg = f"❌ Failed to write usage log: {e}"
        logger.error(redact_log(mask_phi(error_msg)))
        handle_error(e, "USAGE_LOG_WRITE_001")


def get_usage_summary(tenant_id: str, user_id: str) -> dict:
    """
    Returns a summary of usage events for a specific tenant and user.
    """
    path = get_usage_log_path()
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r") as f:
            logs = json.load(f)

        summary = {}
        for entry in logs:
            if entry["tenant_id"] == tenant_id and entry["user_id"] == user_id:
                key = entry["event_type"]
                summary[key] = summary.get(key, 0) + entry["amount"]

        return summary

    except Exception as e:
        error_msg = f"❌ Failed to read usage log: {e}"
        logger.error(redact_log(mask_phi(error_msg)))
        handle_error(e, "USAGE_LOG_READ_001")
        return {}
