import os
import json
import hashlib
from datetime import datetime
from core.session_utils import get_session_temp_dir
from core.security import mask_phi, redact_log
from core.error_handling import handle_error
from logger import logger
from core.billing import record_usage

USAGE_QUOTAS = {
    "openai_tokens": 500000,
    "documents_generated": 10000,
    "emails_sent": 2000
}

def get_usage_log_path(tenant_id: str) -> str:
    try:
        base = get_session_temp_dir()
        tenant_path = os.path.join(base, "usage_logs", tenant_id)
        os.makedirs(tenant_path, exist_ok=True)
        return os.path.join(tenant_path, "usage_log.json")
    except Exception as e:
        handle_error(e, "USAGE_LOG_PATH_001")
        raise

def log_usage(event_type: str, tenant_id: str, user_id: str, amount: int, metadata: dict = None):
    path = get_usage_log_path(tenant_id)
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "tenant_id": tenant_id,
        "user_id": user_id,
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
        logger.info(f"[USAGE_LOG] Event={event_type} Tenant={tenant_id} User={user_id} Amount={amount}")
        try:
            record_usage(metadata.get("subscription_item_id") if metadata else "", amount)
        except Exception as e:
            logger.warning(f"[USAGE_BILLING] Failed to push usage to billing: {e}")
    except Exception as e:
        error_msg = f"❌ Failed to write usage log: {e}"
        logger.error(redact_log(mask_phi(error_msg)))
        handle_error(e, "USAGE_LOG_WRITE_001")

def get_usage_summary(tenant_id: str, user_id: str) -> dict:
    path = get_usage_log_path(tenant_id)
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

def check_quota(tenant_id: str, user_id: str, event_type: str, amount: int = 1) -> bool:
    try:
        summary = get_usage_summary(tenant_id, user_id)
        current = summary.get(event_type, 0)
        limit = USAGE_QUOTAS.get(event_type)
        if limit is None:
            return True
        within_limit = (current + amount) <= limit
        if not within_limit:
            logger.warning(f"[USAGE_QUOTA] Tenant={tenant_id} User={user_id} Event={event_type} Current={current} Limit={limit}")
        return within_limit
    except Exception as e:
        handle_error(e, "USAGE_QUOTA_CHECK_001")
        return False

def enforce_quota(tenant_id: str, user_id: str, event_type: str, amount: int = 1):
    if not check_quota(tenant_id, user_id, event_type, amount):
        error_msg = f"Quota exceeded for {event_type} (tenant={tenant_id}, user={user_id})"
        logger.error(redact_log(mask_phi(error_msg)))
        handle_error(Exception(error_msg), "USAGE_QUOTA_EXCEEDED_001", raise_it=True)

def push_metrics_to_monitoring():
    try:
        logger.info("[METRICS] Pushing usage metrics to monitoring system...")
    except Exception as e:
        handle_error(e, "USAGE_METRICS_PUSH_001")