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

    # --- Floating brain bubble (styled button) ---
    with st.container():
        st.markdown("""
            <style>
            div[data-testid="brain-button"] button {
                position: fixed;
                bottom: 25px;
                left: 25px;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background-color: #0A1D3B;
                box-shadow: 0px 4px 10px rgba(0,0,0,0.3);
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 0;
                z-index: 9999;
            }
            div[data-testid="brain-button"] button span {
                visibility: hidden;
            }
            </style>
        """, unsafe_allow_html=True)
        col = st.columns([0.0001, 0.9999])
        with col[0]:
            if st.button("🧠", key="brain-button"):
                st.session_state.show_assistant = not st.session_state.show_assistant
                # Greet on first open
                if st.session_state.show_assistant and "assistant_greeted" not in st.session_state:
                    welcome = "Hi there! I'm your Legal Automation Assistant. I can help explain outputs, troubleshoot, or fix writing tone."
                    st.session_state.chat_log = st.session_state.get("chat_log", [])
                    st.session_state.chat_log.append({"user": "System", "assistant": welcome})
                    st.session_state.assistant_greeted = True

    # --- Assistant popup modal ---
    if st.session_state.show_assistant:
        with st.container():
            st.markdown("""
                <div style="
                    position: fixed;
                    bottom: 100px;
                    left: 25px;
                    z-index: 9998;
                    width: 380px;
                    max-height: 550px;
                    background: #fff;
                    border-radius: 12px;
                    border: 1px solid #ccc;
                    padding: 1rem;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
                    overflow-y: auto;
                ">
            """, unsafe_allow_html=True)

            # --- Modal Header with Close Button ---
            cols = st.columns([0.85, 0.15])
            with cols[0]:
                st.markdown("### 🧠 Legal Automation Assistant")
                st.caption("How can I help you today? I can answer questions, fix tone, explain outputs, and troubleshoot.")
            with cols[1]:
                if st.button("×", key="close_assistant"):
                    st.session_state.show_assistant = False
                    st.stop()

            # --- Chat history ---
            if "chat_log" not in st.session_state:
                st.session_state.chat_log = []

            for entry in st.session_state.chat_log[-6:]:
                if entry["user"] != "System":
                    st.markdown(f"**You:** {entry['user']}")
                st.markdown(f"**Assistant:** {entry['assistant']}")
                st.markdown("---")

            # --- Prompt input ---
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
