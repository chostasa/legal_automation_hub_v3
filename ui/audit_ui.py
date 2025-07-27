import streamlit as st
from core.auth import get_tenant_id, get_user_id
from core.db import get_audit_events
from core.error_handling import handle_error

def run_ui():
    try:
        st.title("📜 Audit Log Viewer")

        tenant_id = get_tenant_id()
        user_id_filter = st.text_input("🔎 Filter by User ID (optional)")
        action_filter = st.text_input("🔎 Filter by Action (optional)")
        limit = st.slider("Results Limit", min_value=10, max_value=200, value=50, step=10)

        with st.spinner("Loading audit logs..."):
            logs = get_audit_events(
                tenant_id=tenant_id,
                user_id=user_id_filter.strip() or None,
                action=action_filter.strip() or None,
                limit=limit
            )

        if logs:
            st.success(f"✅ Found {len(logs)} audit events")
            st.dataframe(logs, use_container_width=True)

            # Optional: Expand each log for metadata preview
            for log in logs:
                with st.expander(f"{log['timestamp']} – {log['action']} (User: {log.get('user_id','-')})"):
                    st.json(log)
        else:
            st.info("No audit events match your filter.")

    except Exception as e:
        msg = handle_error(e, code="AUDIT_UI_001")
        st.error(msg)
