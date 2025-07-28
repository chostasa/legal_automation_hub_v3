import os
import json
import hashlib
from datetime import datetime
from core.error_handling import handle_error
from logger import logger

USAGE_QUOTAS = {
    "openai_tokens": 500000,
    "documents_generated": 10000,
    "emails_sent": 2000
}


def get_usage_log_path(tenant_id: str = "internal-tenant") -> str:
    """
    Store usage logs in a fixed directory for internal use (no tenant separation).
    """
    base_dir = "data/usage_logs"
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "usage_log.json")


def log_usage(event_type: str, amount: int, metadata: dict = None):
    """
    Log usage without any external dependencies.
    """
    path = get_usage_log_path()
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "amount": amount,
        "metadata": metadata or {},
    }
    log_entry["hash"] = hashlib.sha256(json.dumps(log_entry, sort_keys=True).encode()).hexdigest()

    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append(log_entry)
        with open(path, "w") as f:
            json.dump(logs, f, indent=2)
        logger.info(f"[USAGE_LOG] Event={event_type} Amount={amount}")
    except Exception as e:
        handle_error(e, "USAGE_LOG_WRITE_001")


def get_usage_summary() -> dict:
    path = get_usage_log_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            logs = json.load(f)
        summary = {}
        for entry in logs:
            key = entry["event_type"]
            summary[key] = summary.get(key, 0) + entry["amount"]
        return summary
    except Exception as e:
        handle_error(e, "USAGE_LOG_READ_001")
        return {}


def check_quota(event_type: str, amount: int = 1) -> bool:
    try:
        summary = get_usage_summary()
        current = summary.get(event_type, 0)
        limit = USAGE_QUOTAS.get(event_type)
        if limit is None:
            return True
        return (current + amount) <= limit
    except Exception as e:
        handle_error(e, "USAGE_QUOTA_CHECK_001")
        return False


def get_quota_status() -> dict:
    """
    Return the quota status for all event types.
    """
    summary = get_usage_summary()
    status = {}
    for event_type, limit in USAGE_QUOTAS.items():
        used = summary.get(event_type, 0)
        status[event_type] = {
            "used": used,
            "limit": limit,
            "remaining": max(limit - used, 0),
            "within_limit": used < limit,
        }
    return status
