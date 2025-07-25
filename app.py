import streamlit as st
from logger import logger
import config  # Forces early crash if .env is missing or misconfigured

from core.auth import get_user_id, get_tenant_id
from core.usage_tracker import get_usage_summary

from utils.file_utils import clean_temp_dir
clean_temp_dir()

# === App Config ===
st.set_page_config(page_title="Legal Automation Hub – V3", layout="wide")

# === Header ===
st.markdown("""
<div style="background-color:#0A1D3B;padding:2rem;text-align:center;">
  <h1 style="color:white;">Legal Automation Hub – V3</h1>
  <p style="color:white;">Streamlined document generation and legal automation at scale.</p>
</div>
""", unsafe_allow_html=True)

# === Sidebar: Navigation ===
st.sidebar.title("🛠️ Tools")
tool = st.sidebar.radio("Select a module:", [
    "🧾 Mediation Memos",
    "📂 Demands",
    "📬 FOIA Requests",
    "📄 Batch Doc Generator",
    "📊 Litigation Dashboard",
    "📧 Welcome Email Sender"
    "🧠 Style Mimic Generator"
])

# === Sidebar: Usage Tracker ===
with st.sidebar.expander("📊 Usage Summary"):
    try:
        usage = get_usage_summary(get_tenant_id(), get_user_id())
        st.write("🧠 OpenAI Tokens:", usage.get("openai_tokens", 0))
        st.write("📨 Emails Sent:", usage.get("emails_sent", 0))
    except Exception as e:
        logger.warning(f"Usage summary failed: {e}")
        st.write("⚠️ Unable to load usage summary.")

# === Route to Tool Modules ===
try:
    if tool == "🧾 Mediation Memos":
        from ui.mediation_ui import run_ui
        run_ui()

    elif tool == "📂 Demands":
        from ui.demand_ui import run_ui
        run_ui()

    elif tool == "📬 FOIA Requests":
        from ui.foia_ui import run_ui
        run_ui()

    elif tool == "📄 Batch Doc Generator":
        from ui.batch_ui import run_ui
        run_ui()

    elif tool == "📊 Litigation Dashboard":
        from ui.dashboard_ui import run_ui
        run_ui()

    elif tool == "🧠 Style Mimic Generator":
        from ui.style_transfer_ui import run_style_transfer_ui
        run_ui()

    elif tool == "📧 Welcome Email Sender":
        from ui.email_ui import run_ui
        run_ui()

    else:
        st.error("❌ Unknown module selected.")

except Exception as e:
    import traceback
    st.error("❌ Failed to load selected module. See below.")
    st.exception(e)
    from core.security import redact_log
    st.code(redact_log(traceback.format_exc()))

