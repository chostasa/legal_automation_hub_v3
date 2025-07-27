import streamlit as st
import uuid
import os
from core.auth import get_tenant_id
from core.error_handling import handle_error
from core.security import sanitize_filename
from core.audit import log_audit_event

def get_session_id() -> str:
    try:
        if "session_id" not in st.session_state:
            st.session_state["session_id"] = str(uuid.uuid4())
        return st.session_state["session_id"]
    except Exception as e:
        handle_error(e, "SESSION_UTILS_001")
        raise

def get_session_temp_dir(base_dir: str = "temp") -> str:
    try:
        tenant_id = get_tenant_id()
        session_id = get_session_id()
        safe_tenant = sanitize_filename(tenant_id)
        safe_session = sanitize_filename(session_id)

        path = os.path.join(base_dir, safe_tenant, safe_session)
        os.makedirs(path, exist_ok=True)

        log_audit_event("Session Temp Dir Created", {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "path": path
        })

        return path
    except Exception as e:
        handle_error(e, "SESSION_UTILS_002")
        raise
