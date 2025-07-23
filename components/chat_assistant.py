import streamlit as st
import os
from datetime import datetime
from services.openai_client import safe_generate
from core.auth import get_user_id, get_tenant_id
from core.security import redact_log
from logger import logger

ASSISTANT_SYSTEM_PROMPT = """
You are a helpful internal assistant for litigation staff using the Legal Automation Hub.
You help rephrase legal text, explain outputs, and answer module questions.
"""

def log_assistant_interaction(user, tenant, question, answer):
    try:
        log_dir = os.path.join("logs", "assistant_logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{tenant}_{user}.csv")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()},{question.strip().replace(',', ' ')},{answer.strip().replace(',', ' ')}\n")
    except Exception as e:
        logger.error(redact_log(f"❌ Assistant log failed: {e}"))

def render_chat_modal():
    if "show_assistant" not in st.session_state:
        st.session_state.show_assistant = False

    # Inject custom CSS for floating layout
    st.markdown("""
        <style>
        .chat-bubble {
            position: fixed;
            bottom: 25px;
            left: 25px;
            z-index: 9999;
        }
        .chat-modal {
            position: fixed;
            bottom: 100px;
            left: 25px;
            z-index: 9998;
            background: white;
            border: 2px solid #0A1D3B;
            border-radius: 12px;
            padding: 1rem;
            width: 360px;
            max-height: 500px;
            overflow-y: auto;
            box-shadow: 0px 6px 15px rgba(0,0,0,0.25);
        }
        </style>
    """, unsafe_allow_html=True)

    # === Floating Button
    with st.container():
        chat_toggle = st.button("💬", key="chat_toggle", help="Toggle Assistant", args=(), kwargs={}, use_container_width=False)
        if chat_toggle:
            st.session_state.show_assistant = not st.session_state.show_assistant

    # === Floating Modal if Active
    if st.session_state.show_assistant:
        st.markdown('<div class="chat-modal">', unsafe_allow_html=True)
        st.markdown("#### 🧠 Legal Automation Assistant")

        if "chat_log" not in st.session_state:
            st.session_state.chat_log = []

        for entry in st.session_state.chat_log[-5:]:
            st.markdown(f"**You:** {entry['user']}")
            st.markdown(f"**Assistant:** {entry['assistant']}")
            st.markdown("---")

        prompt = st.text_input("Ask the assistant...", key="assistant_input")
        if prompt:
            try:
                response = safe_generate(prompt, system_msg=ASSISTANT_SYSTEM_PROMPT)
            except Exception as e:
                response = "❌ Something went wrong."
                logger.error(redact_log(f"❌ Assistant failed: {e}"))

            st.session_state.chat_log.append({"user": prompt, "assistant": response})
            log_assistant_interaction(get_user_id(), get_tenant_id(), prompt, response)
            st.experimental_rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # === Floating Button Div (overlay)
    st.markdown('<div class="chat-bubble"></div>', unsafe_allow_html=True)
