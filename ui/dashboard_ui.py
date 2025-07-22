import streamlit as st
import pandas as pd
from services.dropbox_client import download_dashboard_df
from core.security import sanitize_text, redact_log
from logger import logger

def run_ui():
    st.header("📊 Litigation Campaign Dashboard")

    try:
        df = download_dashboard_df()
        if df.empty:
            st.warning("⚠️ The dashboard is currently empty.")
            return
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to load dashboard: {e}"))
        st.error("❌ Could not load dashboard data.")
        return

    # === Filter UI ===
    st.sidebar.title("🔍 Filters")

    campaigns = df["Case Type"].dropna().unique().tolist()
    campaign_filter = st.sidebar.selectbox("Filter by Campaign", ["All"] + sorted(campaigns))

    if campaign_filter != "All":
        df = df[df["Case Type"] == campaign_filter]

    # === KPI Summary ===
    st.subheader("📈 Case Status Overview")
    if "Class Code Title" in df.columns:
        status_counts = df["Class Code Title"].value_counts()
        st.bar_chart(status_counts)
    else:
        st.info("ℹ️ No 'Class Code Title' data to display.")

    st.subheader("👨‍⚖️ Referring Attorney Overview")
    if "Referring Attorney" in df.columns:
        referral_counts = df["Referring Attorney"].value_counts()
        st.bar_chart(referral_counts)
    else:
        st.info("ℹ️ No 'Referring Attorney' data to display.")

    # === Table View ===
    st.subheader("📋 Case Table")
    table_fields = ["Client Name", "Case Type", "Class Code Title", "Referring Attorney", "Phone Number", "Email"]
    filtered_fields = [col for col in table_fields if col in df.columns]

    if filtered_fields:
        display_df = df[filtered_fields].copy()
        for col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda x: sanitize_text(str(x)))
        st.dataframe(display_df.reset_index(drop=True))
    else:
        st.warning("⚠️ No matching fields found to display.")

    # === Download Option ===
    st.download_button(
        label="⬇️ Download Current Filtered Data",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="filtered_dashboard.csv",
        mime="text/csv"
    )
