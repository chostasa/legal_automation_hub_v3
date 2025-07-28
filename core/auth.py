def get_user_id() -> str:
    """
    Return a fixed user ID for internal use.
    """
    return "internal-user"


def get_tenant_id() -> str:
    """
    Return a fixed tenant ID for internal use.
    """
    return "internal-tenant"


def get_user_role() -> str:
    """
    Return 'admin' for all internal users.
    """
    return "admin"


def user_has_permission(permission: str) -> bool:
    """
    All internal users have permission.
    """
    return True


def enforce_permission(permission: str):
    """
    Decorator that does nothing (all permissions allowed internally).
    """
    def decorator(func):
        return func
    return decorator


def enforce_tenant_scope(path: str) -> str:
    """
    For internal use, just return the path unchanged.
    """
    return path


def enforce_quota(event_type: str, amount: int = 1):
    """
    Decorator that does nothing for internal use.
    """
    def decorator(func):
        return func
    return decorator


def map_domain_to_tenant(domain: str) -> str:
    """
    Always return the internal tenant ID.
    """
    return "internal-tenant"


def get_tenant_branding(tenant_id: str = "internal-tenant") -> dict:
    """
    Return basic branding for internal firm use.
    """
    return {
        "firm_name": "Legal Automation Hub (Internal)",
        "logo": "",
        "primary_color": "#0A1D3B"
    }
