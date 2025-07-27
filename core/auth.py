# core/auth.py
from core.error_handling import handle_error

def get_user_id():
    try:
        return "test-user"
    except Exception as e:
        handle_error(e, "AUTH_USER_001")
        return None

def get_tenant_id():
    try:
        return "test-tenant"
    except Exception as e:
        handle_error(e, "AUTH_TENANT_001")
        return None
