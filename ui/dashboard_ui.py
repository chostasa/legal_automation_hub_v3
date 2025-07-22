import streamlit as st
import pandas as pd
import plotly.express as px
from services.dropbox_client import DropboxClient
from core.security import sanitize_text, redact_log
from logger import logger

@st.cache_data(ttl=300)
def load_dashboard_data():
    client = DropboxClient()
    return client.download_dashboard_df()

def run_ui():
    st.title("📊 Litigation Campaign Dashboard")

    try:
        df = load_dashboard_data()
        if df.empty:
            st.warning("⚠️ The dashboard is currently empty.")
            return
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to load dashboard: {e}"))
        st.error("❌ Could not load dashboard data.")
        return

    # Normalize column names (remove whitespace)
    df.columns = df.columns.str.strip()

    # Define key column names
    CAMPAIGN_COL = "Case Type"
    STATUS_COL = "Class Code Title"
    REFERRAL_COL = "Referred By Name (Full - Last, First)"

    # === Base Filters ===
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

    # === Optional Filters ===
    st.sidebar.header("⚙️ Optional Filters")
    base_cols = [CAMPAIGN_COL, REFERRAL_COL, STATUS_COL]

    for col in filtered_df.columns:
        if col not in base_cols and 1 < filtered_df[col].nunique() < 25:
            values = st.sidebar.multiselect(f"{col}", sorted(filtered_df[col].dropna().unique()))
            if values:
                filtered_df = filtered_df[filtered_df[col].isin(values)]

    # === KPI Charts ===
    st.subheader("📌 Case Status Overview")
    if STATUS_COL in filtered_df.columns:
        status_counts = filtered_df[STATUS_COL].value_counts().reset_index()
        status_counts.columns = ["Case Status", "Count"]
        fig_status = px.bar(status_counts, x="Case Status", y="Count", text="Count")
        st.plotly_chart(fig_status, use_container_width=True)

    st.subheader("👤 Referring Attorney Overview")
    if REFERRAL_COL in filtered_df.columns:
        referral_counts = filtered_df[REFERRAL_COL].value_counts().reset_index()
        referral_counts.columns = ["Referring Attorney", "Count"]
        fig_ref = px.bar(referral_counts, x="Referring Attorney", y="Count", text="Count")
        st.plotly_chart(fig_ref, use_container_width=True)

    # === Case Table ===
    st.subheader(f"📋 Filtered Case Table ({len(filtered_df)} records)")
    display_cols = [
        "Case Type",
        "Class Code Title",
        "Date Opened",
        "Referred By Name (Full - Last, First)",
        "Case Details First Party Name (Full - Last, First)",
        "Case Details First Party Details Default Phone Number",
        "Case Details First Party Details Default Email Account Address"
    ]

    shown_cols = [col for col in display_cols if col in filtered_df.columns]
    clean_df = filtered_df[shown_cols].copy()

    for col in clean_df.columns:
        clean_df[col] = clean_df[col].apply(lambda x: sanitize_text(str(x)))

    st.dataframe(clean_df.reset_index(drop=True), use_container_width=True)

    # === Download CSV ===
    st.download_button(
        label="⬇️ Download Filtered Results as CSV",
        data=filtered_df.to_csv(index=False).encode("utf-8"),
        file_name="filtered_dashboard.csv",
        mime="text/csv"
    )
