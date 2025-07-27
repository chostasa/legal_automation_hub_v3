from core.auth import get_user_id, get_tenant_id
from core.security import sanitize_text, mask_phi, redact_log
from core.error_handling import handle_error
from core.db import insert_audit_event, get_audit_events


def log_audit_event(action: str, metadata: dict = None):
    """
    Log a structured audit event to the database with user and tenant context.
    """
    try:
        tenant_id = get_tenant_id()
        user_id = get_user_id()

        clean_metadata = {}
        if metadata:
            for k, v in metadata.items():
                clean_metadata[sanitize_text(str(k))] = sanitize_text(str(v))

        insert_audit_event(
            tenant_id=tenant_id,
            user_id=user_id,
            action=sanitize_text(action),
            metadata=clean_metadata
        )

    except Exception as e:
        safe_error = redact_log(mask_phi(f"❌ Failed to write audit log: {e}"))
        handle_error(safe_error, code="AUDIT_LOG_001")


def fetch_audit_events(user_id: str = None, action: str = None, limit: int = 50):
    """
    Retrieve audit events for the current tenant with optional filters.
    """
    try:
        tenant_id = get_tenant_id()
        return get_audit_events(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            limit=limit
        )
    except Exception as e:
        safe_error = redact_log(mask_phi(f"❌ Failed to fetch audit events: {e}"))
        handle_error(safe_error, code="AUDIT_LOG_002", raise_it=True)
