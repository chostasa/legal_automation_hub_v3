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
    # Set default state
    if "show_assistant" not in st.session_state:
        st.session_state.show_assistant = False

    # === Bubble toggle button (bottom-left)
    st.markdown("""
        <style>
        .chat-toggle {
            position: fixed;
            bottom: 20px;
            left: 20px;
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
        <button class="chat-toggle" onclick="window.parent.postMessage({ type: 'toggle-chat' }, '*')">💬</button>
        <script>
        window.addEventListener("message", (event) => {
            if (event.data.type === "toggle-chat") {
                const streamlitInput = window.parent.document.querySelector('iframe');
                streamlitInput.contentWindow.postMessage({ type: "streamlit:rerun" }, "*");
                fetch("/_stcore/_broadcast", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ event: "toggle_chat_state" })
                });
            }
        });
        </script>
    """, unsafe_allow_html=True)

    # === Manual toggle (Streamlit state-based) — safe fallback
    toggle = st.experimental_get_query_params().get("chat", [None])[0]
    if toggle == "show":
        st.session_state.show_assistant = True
    elif toggle == "hide":
        st.session_state.show_assistant = False

    # === Render Assistant if visible
    if st.session_state.show_assistant:
        with st.expander("🧠 Legal Automation Assistant", expanded=True):
            if "chat_log" not in st.session_state:
                st.session_state.chat_log = []

            for entry in st.session_state.chat_log:
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
