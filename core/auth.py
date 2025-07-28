import os
import functools
from core.error_handling import handle_error
from core.security import sanitize_text

ROLES = {
    "admin": ["view_audit_logs", "manage_templates", "manage_users"],
    "staff": ["generate_documents", "send_emails"]
}


def get_user_id():
    try:
        return os.environ.get("USER_ID", "test-user")
    except Exception as e:
        handle_error(e, "AUTH_USER_001")
        return None


def get_tenant_id():
    try:
        return os.environ.get("TENANT_ID", "test-tenant")
    except Exception as e:
        handle_error(e, "AUTH_TENANT_001")
        return None


def get_user_role():
    try:
        return os.environ.get("USER_ROLE", "staff").lower()
    except Exception as e:
        handle_error(e, "AUTH_ROLE_001")
        return "staff"


def user_has_permission(permission: str) -> bool:
    try:
        role = get_user_role()
        return permission in ROLES.get(role, [])
    except Exception as e:
        handle_error(e, "AUTH_PERM_001")
        return False


def enforce_permission(permission: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not user_has_permission(permission):
                handle_error(Exception("Permission denied"), "AUTH_PERM_002")
                raise PermissionError(f"User lacks permission: {permission}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def enforce_tenant_scope(path: str) -> str:
    try:
        tenant_id = sanitize_text(get_tenant_id())
        return os.path.join("data", tenant_id, path)
    except Exception as e:
        handle_error(e, "AUTH_SCOPE_001")
        return path


def enforce_quota(event_type: str, amount: int = 1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Lazy import to break circular import
            from core.usage_tracker import check_quota
            
            tenant_id = get_tenant_id()
            user_id = get_user_id()
            if not check_quota(tenant_id, user_id, event_type, amount):
                handle_error(Exception("Quota exceeded"), "AUTH_QUOTA_001")
                raise RuntimeError(f"Quota exceeded for event: {event_type}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def map_domain_to_tenant(domain: str) -> str:
    try:
        mapping = {
            "firm1.legalhub.app": "tenant_firm1",
            "firm2.legalhub.app": "tenant_firm2"
        }
        return mapping.get(domain, "test-tenant")
    except Exception as e:
        handle_error(e, "AUTH_DOMAIN_001")
        return "test-tenant"


def get_tenant_branding(tenant_id: str) -> dict:
    try:
        branding_config = {
            "tenant_firm1": {"firm_name": "Firm 1 Legal Hub", "logo": "data/tenant_firm1/logo.png", "primary_color": "#123456"},
            "tenant_firm2": {"firm_name": "Firm 2 Legal Hub", "logo": "data/tenant_firm2/logo.png", "primary_color": "#654321"},
            "test-tenant": {"firm_name": "Legal Automation Hub", "logo": "", "primary_color": "#0A1D3B"}
        }
        return branding_config.get(tenant_id, branding_config["test-tenant"])
    except Exception as e:
        handle_error(e, "AUTH_BRAND_001")
        return {"firm_name": "Legal Automation Hub", "logo": "", "primary_color": "#0A1D3B"}
