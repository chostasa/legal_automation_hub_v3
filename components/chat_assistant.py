import streamlit as st
from services.openai_client import safe_generate
from core.auth import get_user_id, get_tenant_id
from core.security import redact_log
from logger import logger
import os
from datetime import datetime

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
    # Handle toggle
    if "show_assistant" not in st.session_state:
        st.session_state.show_assistant = False

    # Floating chat bubble button
    st.markdown("""
    <style>
        #chat-toggle-button {
            position: fixed;
            bottom: 25px;
            left: 25px;
            background-color: #0A1D3B;
            color: white;
            border: none;
            border-radius: 50%;
            width: 55px;
            height: 55px;
            font-size: 26px;
            text-align: center;
            z-index: 9999;
            cursor: pointer;
        }
    </style>
    <button id="chat-toggle-button" onclick="window.parent.postMessage({type: 'toggle_chat'}, '*')">💬</button>
    <script>
        const streamlitDoc = window.parent.document;

        window.addEventListener("message", (event) => {
            if (event.data.type === "toggle_chat") {
                const input = streamlitDoc.querySelector('input[data-testid="stTextInput"][aria-label="assistant_input"]');
                if (input) {
                    input.closest('div[data-testid="stVerticalBlock"]').style.display =
                        input.closest('div[data-testid="stVerticalBlock"]').style.display === "none"
                        ? "block" : "none";
                }
            }
        });
    </script>
    """, unsafe_allow_html=True)

    # === Assistant Panel ===
    with st.container():
        st.markdown("### 🧠 Legal Automation Assistant")
        if "chat_log" not in st.session_state:
            st.session_state.chat_log = []

        for entry in st.session_state.chat_log:
            st.markdown(f"**You:** {entry['user']}")
            st.markdown(f"**Assistant:** {entry['assistant']}")
            st.markdown("---")

        user_input = st.text_input("Ask the assistant...", key="assistant_input")
        if user_input:
            with st.spinner("💭 Thinking..."):
                try:
                    reply = safe_generate(user_input, system_msg=ASSISTANT_SYSTEM_PROMPT)
                except Exception as e:
                    reply = "❌ Sorry, something went wrong."
                    logger.error(redact_log(f"❌ Assistant failed: {e}"))

            st.session_state.chat_log.append({
                "user": user_input,
                "assistant": reply
            })
            log_assistant_interaction(get_user_id(), get_tenant_id(), user_input, reply)
            st.experimental_rerun()
