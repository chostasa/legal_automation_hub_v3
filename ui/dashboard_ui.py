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

    # ========== 🔍 Filter Sidebar ==========
    st.sidebar.header("Primary Filters")
    campaign_filter = st.sidebar.multiselect("📁 Campaign", sorted(df["Case Type"].dropna().unique()))
    referring_filter = st.sidebar.multiselect("👤 Referring Attorney", sorted(df["Referring Attorney"].dropna().unique()))
    status_filter = st.sidebar.multiselect("📌 Case Status", sorted(df["Class Code Title"].dropna().unique()))

    filtered_df = df.copy()
    if campaign_filter:
        filtered_df = filtered_df[filtered_df["Case Type"].isin(campaign_filter)]
    if referring_filter:
        filtered_df = filtered_df[filtered_df["Referring Attorney"].isin(referring_filter)]
    if status_filter:
        filtered_df = filtered_df[filtered_df["Class Code Title"].isin(status_filter)]

    # ========== ⚙️ Optional Dynamic Filters ==========
    st.sidebar.header("Optional Filters")
    base_filters = ["Case Type", "Referring Attorney", "Class Code Title"]
    for col in filtered_df.columns:
        if col not in base_filters and 1 < filtered_df[col].nunique() < 25:
            values = st.sidebar.multiselect(f"{col}", sorted(filtered_df[col].dropna().unique()))
            if values:
                filtered_df = filtered_df[filtered_df[col].isin(values)]

    # ========== 🧭 KPI Overview ==========
    st.subheader("📌 Key Insights")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Cases", f"{len(filtered_df)}")
    if "Class Code Title" in filtered_df.columns:
        top_status = filtered_df["Class Code Title"].value_counts().idxmax()
        col2.metric("Most Common Status", top_status)
    if "Referring Attorney" in filtered_df.columns:
        top_attorney = filtered_df["Referring Attorney"].value_counts().idxmax()
        col3.metric("Top Referring Atty", top_attorney)

    # ========== 📊 Visualizations ==========
    if "Class Code Title" in filtered_df.columns:
        st.subheader("📊 Case Status Distribution")
        status_counts = filtered_df["Class Code Title"].value_counts().reset_index()
        status_counts.columns = ["Case Status", "Count"]
        fig_status = px.bar(
            status_counts, x="Case Status", y="Count", text="Count", title="Case Status Overview",
            color="Case Status"
        )
        fig_status.update_traces(textposition="outside")
        st.plotly_chart(fig_status, use_container_width=True)

    if "Referring Attorney" in filtered_df.columns:
        st.subheader("👥 Referring Attorney Distribution")
        referral_counts = filtered_df["Referring Attorney"].value_counts().reset_index()
        referral_counts.columns = ["Referring Attorney", "Count"]
        fig_referrals = px.pie(
            referral_counts, values="Count", names="Referring Attorney",
            title="Case Distribution by Referring Attorney", hole=0.4
        )
        st.plotly_chart(fig_referrals, use_container_width=True)

    if "Case Type" in filtered_df.columns:
        st.subheader("📁 Campaign Breakdown")
        case_counts = filtered_df["Case Type"].value_counts().reset_index()
        case_counts.columns = ["Campaign", "Count"]
        fig_campaigns = px.bar(
            case_counts, x="Campaign", y="Count", text="Count", title="Cases per Campaign",
            color="Campaign"
        )
        fig_campaigns.update_traces(textposition="outside")
        st.plotly_chart(fig_campaigns, use_container_width=True)

    # ========== 📋 Data Table ==========
    st.subheader(f"📄 Filtered Case Table ({len(filtered_df)} records)")
    display_cols = ["Client Name", "Case Type", "Class Code Title", "Referring Attorney", "Phone Number", "Email"]
    columns_to_show = [col for col in display_cols if col in filtered_df.columns]

    if columns_to_show:
        safe_df = filtered_df[columns_to_show].copy()
        for col in safe_df.columns:
            safe_df[col] = safe_df[col].apply(lambda x: sanitize_text(str(x)))
        st.dataframe(safe_df.reset_index(drop=True), use_container_width=True)
    else:
        st.warning("⚠️ No matching columns to display.")

    # ========== ⬇️ Download ==========
    st.download_button(
        label="⬇️ Download Filtered CSV",
        data=filtered_df.to_csv(index=False).encode("utf-8"),
        file_name="litigation_dashboard_filtered.csv",
        mime="text/csv"
    )
