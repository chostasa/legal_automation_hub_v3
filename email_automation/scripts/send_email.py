# send_email.py

import requests
from datetime import datetime
import streamlit as st

GRAPH_URL = "https://graph.microsoft.com/v1.0"

def get_access_token():
    tenant_id = st.secrets["graph_tenant_id"]
    client_id = st.secrets["graph_client_id"]
    client_secret = st.secrets["graph_client_secret"]

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_id": client_id,
        "scope": "https://graph.microsoft.com/.default",
        "client_secret": client_secret,
        "grant_type": "client_credentials"
    }

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

def send_email(to, subject, body, cc=[]):
    token = get_access_token()
    from_email = st.secrets["graph_sender_email"]

    message = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body
            },
            "toRecipients": [{"emailAddress": {"address": to}}],
            "ccRecipients": [{"emailAddress": {"address": addr}} for addr in cc],
        },
        "saveToSentItems": "true"
    }

    url = f"{GRAPH_URL}/users/{from_email}/sendMail"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    response = requests.post(url, headers=headers, json=message)
    response.raise_for_status()
    return True
