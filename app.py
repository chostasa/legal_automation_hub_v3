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

# === Page Mapping ===
from ui import instructions_ui, mediation_ui, demand_ui, foia_ui, batch_ui, dashboard_ui, email_ui, style_transfer_ui, template_tester_ui

PAGES = {
    "📖 Instructions": instructions_ui,
    "🧾 Mediation Memos": mediation_ui,
    "📂 Demands": demand_ui,
    "📬 FOIA Requests": foia_ui,
    "📄 Batch Doc Generator": batch_ui,
    "📊 Litigation Dashboard": dashboard_ui,
    "📧 Welcome Email Sender": email_ui,
    "🧠 Style Mimic Generator": style_transfer_ui,
    "🧪 Template Tester": template_tester_ui
}

# === Sidebar: Navigation ===
st.sidebar.title("🛠️ Tools")
tool = st.sidebar.radio("Select a module:", list(PAGES.keys()))

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
    # Dynamically call the selected page's run_ui()
    page_module = PAGES[tool]
    if hasattr(page_module, "run_ui"):
        page_module.run_ui()
    elif hasattr(page_module, "run_style_transfer_ui"):
        # Style Mimic uses a different function name
        page_module.run_style_transfer_ui()
    else:
        st.error("❌ Module does not have a run_ui() function.")
except Exception as e:
    import traceback
    st.error("❌ Failed to load selected module. See below.")
    st.exception(e)
    from core.security import redact_log
    st.code(redact_log(traceback.format_exc()))
