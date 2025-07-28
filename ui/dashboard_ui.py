import streamlit as st
import pandas as pd
import plotly.express as px
from services.dropbox_client import DropboxClient
from core.security import sanitize_text, redact_log, mask_phi
from utils.file_utils import clean_temp_dir
from core.usage_tracker import log_usage, get_usage_summary
from core.auth import get_user_id, get_tenant_id, get_user_role, get_tenant_branding
from core.error_handling import handle_error
from core.db import insert_audit_event
from logger import logger
import time

clean_temp_dir()

@st.cache_data(ttl=300)
def load_dashboard_data():
    client = DropboxClient()
    return client.download_dashboard_df()

def run_ui():
    tenant_id = get_tenant_id()
    branding = get_tenant_branding(tenant_id)
    st.title(f"📊 {branding.get('firm_name', 'Litigation Campaign Dashboard')}")

    try:
        role = get_user_role()
        usage_summary = get_usage_summary(tenant_id, get_user_id())
        st.sidebar.info(f"🔒 Role: {role} | OpenAI Tokens Used: {usage_summary.get('openai_tokens', 0)}")
    except Exception:
        pass

    error_code = "DASH_001"
    try:
        with st.spinner("📥 Loading dashboard data..."):
            start_time = time.time()
            df = load_dashboard_data()
            load_duration = round(time.time() - start_time, 2)
            logger.info(f"[METRICS] Dashboard data loaded in {load_duration}s")
        if df.empty:
            st.warning("⚠️ The dashboard is currently empty.")
            return
    except Exception as e:
        msg = handle_error(e, code=error_code, user_message="Could not load dashboard data.")
        st.error(msg)
        return

    try:
        df.columns = df.columns.str.strip()
        CAMPAIGN_COL = "Case Type"
        STATUS_COL = "Class Code Title"
        REFERRAL_COL = "Referred By Name (Full - Last, First)"

        st.sidebar.header("🔍 Base Filters")
        campaign_filter = st.sidebar.multiselect("📁 Campaign", sorted(df[CAMPAIGN_COL].dropna().unique()))
        referring_filter = st.sidebar.multiselect("👤 Referring Attorney", sorted(df[REFERRAL_COL].dropna().unique()))
        status_filter = st.sidebar.multiselect("📌 Case Status", sorted(df[STATUS_COL].dropna().unique()))

        filtered_df = df.copy()
        if campaign_filter:
            filtered_df = filtered_df[filtered_df[CAMPAIGN_COL].isin(campaign_filter)]
        if referring_filter:
            filtered_df = filtered_df[filtered_df[REFERRAL_COL].isin(referring_filter)]
        if status_filter:
            filtered_df = filtered_df[filtered_df[STATUS_COL].isin(status_filter)]

        st.subheader("📌 Case Status Overview")
        if STATUS_COL in filtered_df.columns:
            status_counts = filtered_df[STATUS_COL].value_counts().reset_index()
            status_counts.columns = ["Case Status", "Count"]
            st.plotly_chart(px.bar(status_counts, x="Case Status", y="Count", text="Count"), use_container_width=True)

        st.subheader("👤 Referring Attorney Overview")
        if REFERRAL_COL in filtered_df.columns:
            referral_counts = filtered_df[REFERRAL_COL].value_counts().reset_index()
            referral_counts.columns = ["Referring Attorney", "Count"]
            st.plotly_chart(px.bar(referral_counts, x="Referring Attorney", y="Count", text="Count"), use_container_width=True)

        st.subheader("➕ Add Optional Columns")
        optional_display_cols = []
        optional_filtered_cols = []

        with st.expander("Show/Filter Additional Columns"):
            candidate_cols = [
                col for col in df.columns
                if col not in [CAMPAIGN_COL, STATUS_COL, REFERRAL_COL]
                and col not in [
                    "Date Opened",
                    "Case Details First Party Name (Full - Last, First)",
                    "Case Details First Party Details Default Phone Number",
                    "Case Details First Party Details Default Email Account Address"
                ]
            ]
            selected_display_cols = st.multiselect("📌 Choose columns to ADD to the table", candidate_cols)

            for col in selected_display_cols:
                optional_display_cols.append(col)
                if 1 < df[col].nunique() < 50:
                    try:
                        vals = df[col].dropna().astype(str).unique().tolist()
                        selected_vals = st.multiselect(f"Filter values for {col}", sorted(vals), key=col)
                        if selected_vals:
                            filtered_df = filtered_df[filtered_df[col].astype(str).isin(selected_vals)]
                            optional_filtered_cols.append(col)
                    except Exception as e:
                        logger.warning(redact_log(mask_phi(f"⚠️ Could not filter column {col}: {e}")))

        st.subheader(f"📋 Case Table ({len(filtered_df)} records)")
        base_display_cols = [
            "Case Type",
            "Class Code Title",
            "Date Opened",
            "Referred By Name (Full - Last, First)",
            "Case Details First Party Name (Full - Last, First)",
            "Case Details First Party Details Default Phone Number",
            "Case Details First Party Details Default Email Account Address"
        ]

        all_display_cols = [col for col in base_display_cols if col in filtered_df.columns] + optional_display_cols
        clean_df = filtered_df[all_display_cols].copy()
        for col in clean_df.columns:
            clean_df[col] = clean_df[col].apply(lambda x: sanitize_text(str(x)))

        st.dataframe(clean_df.reset_index(drop=True), use_container_width=True)

        if st.button("📤 Send to Batch Generator"):
            try:
                st.session_state.dashboard_df = filtered_df[all_display_cols].copy()
                st.success("✅ Data sent! Go to the '📄 Batch Doc Generator' to merge.")
                insert_audit_event(
                    tenant_id=get_tenant_id(),
                    user_id=get_user_id(),
                    action="Dashboard Data Sent to Batch Generator",
                    metadata={"record_count": len(filtered_df)}
                )
                logger.info(f"[METRICS] Data sent to Batch Generator for {len(filtered_df)} records")
            except Exception as e:
                msg = handle_error(e, code="DASH_002", user_message="Failed to send data to Batch Generator.")
                st.error(msg)

        st.download_button(
            label="⬇️ Download Filtered Results as CSV",
            data=filtered_df[all_display_cols].to_csv(index=False).encode("utf-8"),
            file_name="filtered_dashboard.csv",
            mime="text/csv"
        )

        if campaign_filter or status_filter or referring_filter:
            try:
                log_usage(
                    event_type="dashboard_view",
                    tenant_id=get_tenant_id(),
                    user_id=get_user_id(),
                    amount=len(filtered_df),
                    metadata={
                        "filters": {
                            "campaign": campaign_filter,
                            "status": status_filter,
                            "referral": referring_filter,
                            "extras": optional_filtered_cols
                        }
                    }
                )
                logger.info(f"[METRICS] Dashboard view logged with {len(filtered_df)} records")
            except Exception as log_err:
                logger.warning(redact_log(mask_phi(f"⚠️ Failed to log dashboard usage: {log_err}")))

    except Exception as e:
        msg = handle_error(e, code="DASH_003", user_message="An error occurred in the Dashboard UI.")
        logger.error(redact_log(mask_phi(f"[METRICS] Dashboard UI error: {e}")))
        st.error(msg)