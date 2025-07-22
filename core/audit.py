# core/audit.py

import os
import csv
from datetime import datetime
from core.auth import get_user_id, get_tenant_id
from core.security import sanitize_text

AUDIT_LOG_PATH = os.path.join("logs", "audit_events.csv")
os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)

def log_audit_event(action: str, metadata: dict):
    """Log a structured audit event to CSV with user context."""
    try:
        row = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": get_user_id(),
            "tenant_id": get_tenant_id(),
            "action": sanitize_text(action),
            **{k: sanitize_text(str(v)) for k, v in metadata.items()}
        }

        write_header = not os.path.exists(AUDIT_LOG_PATH)
        with open(AUDIT_LOG_PATH, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    except Exception as e:
        from logger import logger
        logger.error(f"❌ Failed to write audit log: {e}")
