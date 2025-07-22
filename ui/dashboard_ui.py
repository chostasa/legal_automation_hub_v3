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

    df.columns = df.columns.str.strip()

    # === Constants ===
    CAMPAIGN_COL = "Case Type"
    STATUS_COL = "Class Code Title"
    REFERRAL_COL = "Referred By Name (Full - Last, First)"

    # === 🔍 Sidebar Base Filters ===
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

    # === 📊 KPI Charts ===
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

    # === ➕ Optional Filters ===
    st.subheader("➕ Add Optional Filters")

    optional_display_cols = []
    with st.expander("Add Filters from Additional Columns"):
        candidate_cols = [
            col for col in df.columns
            if col not in [CAMPAIGN_COL, STATUS_COL, REFERRAL_COL]
            and 1 < df[col].nunique() < 50
        ]

        selected_col = st.selectbox("Choose a column to filter by", [""] + candidate_cols)
        if selected_col:
            try:
                unique_vals = df[selected_col].dropna().astype(str).unique().tolist()
                selected_vals = st.multiselect(f"Select values for: {selected_col}", sorted(unique_vals), key=selected_col)
                if selected_vals:
                    filtered_df = filtered_df[filtered_df[selected_col].astype(str).isin(selected_vals)]
                    optional_display_cols.append(selected_col)
            except Exception as e:
                st.warning(f"⚠️ Could not apply filter for {selected_col}: {e}")

    # === 📋 Case Table ===
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

    # Show base + any selected optional filters
    all_display_cols = [col for col in base_display_cols if col in filtered_df.columns] + optional_display_cols
    clean_df = filtered_df[all_display_cols].copy()

    for col in clean_df.columns:
        clean_df[col] = clean_df[col].apply(lambda x: sanitize_text(str(x)))

    st.dataframe(clean_df.reset_index(drop=True), use_container_width=True)

    # === ⬇️ Download Button ===
    st.download_button(
        label="⬇️ Download Filtered Results as CSV",
        data=filtered_df.to_csv(index=False).encode("utf-8"),
        file_name="filtered_dashboard.csv",
        mime="text/csv"
    )
