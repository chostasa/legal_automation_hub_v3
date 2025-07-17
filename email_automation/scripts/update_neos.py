# update_neos.py

import os
import requests
from datetime import datetime
import json
CLASS_CODES = json.loads(os.environ.get("CLASS_CODES", "{}"))

def update_class_code(case_id, new_class_code_title, welcome_email_field_key=None):
    base_url = os.environ.get("NEOS_BASE_URL", "https://app.neosconnect.com/api/v1")
    token = os.environ.get("NEOS_API_KEY")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    new_code_id = CLASS_CODES.get(new_class_code_title)
    if not new_code_id:
        raise ValueError(f"Unknown class code title: {new_class_code_title}")

    data = {
        "ClassCodeID": new_code_id
    }

    if welcome_email_field_key:
        today = datetime.now().strftime("%Y-%m-%dT00:00:00Z")
        data[welcome_email_field_key] = today  # ISO 8601 format

    url = f"{base_url}/cases/{case_id}"
    response = requests.patch(url, headers=headers, json=data)
    response.raise_for_status()
    return response.status_code == 200
