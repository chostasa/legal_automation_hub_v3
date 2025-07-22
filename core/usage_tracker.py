import os
import json
from datetime import datetime
from pathlib import Path
from core.session import get_secure_temp_dir

def get_usage_log_path():
    base = get_secure_temp_dir()
    return os.path.join(base, "usage_log.json")

def log_usage(event_type: str, tenant_id: str, user_id: str, amount: int, metadata: dict = None):
    path = get_usage_log_path()
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "amount": amount,
        "metadata": metadata or {},
    }

    if os.path.exists(path):
        with open(path, "r") as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(log_entry)

    with open(path, "w") as f:
        json.dump(logs, f, indent=2)

def get_usage_summary(tenant_id: str, user_id: str):
    path = get_usage_log_path()
    if not os.path.exists(path):
        return {}

    with open(path, "r") as f:
        logs = json.load(f)

    summary = {}
    for entry in logs:
        if entry["tenant_id"] == tenant_id and entry["user_id"] == user_id:
            key = entry["event_type"]
            summary[key] = summary.get(key, 0) + entry["amount"]

    return summary
