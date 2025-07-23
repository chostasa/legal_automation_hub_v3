import streamlit as st
import streamlit.components.v1 as components
from services.openai_client import safe_generate
from core.auth import get_user_id, get_tenant_id
from core.security import redact_log
from logger import logger
import os
from datetime import datetime

ASSISTANT_SYSTEM_PROMPT = """
You are an internal assistant for litigation staff at a law firm.
You help with tone, writing style, legal phrasing, and troubleshooting technical issues.
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
    with st.container():
        st.markdown("""
        <style>
        #chat-bubble {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background-color: #0A1D3B;
            color: white;
            border-radius: 50%;
            width: 55px;
            height: 55px;
            text-align: center;
            font-size: 30px;
            z-index: 1000;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        #chat-box {
            position: fixed;
            bottom: 90px;
            right: 20px;
            width: 350px;
            max-height: 500px;
            background-color: white;
            border: 1px solid #ccc;
            border-radius: 10px;
            overflow-y: auto;
            padding: 1rem;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        </style>

        <div id="chat-bubble" onclick="toggleChat()">💬</div>
        <script>
        const toggleChat = () => {
            const box = window.parent.document.getElementById("chat-box-wrapper");
            box.style.display = box.style.display === "none" ? "block" : "none";
        };
        </script>
        """, unsafe_allow_html=True)

        # Chat wrapper container
        components.html(f"""
        <div id="chat-box-wrapper" style="display: none;">
            <div id="chat-box">
                <h4>💬 Internal Assistant</h4>
                <div id="chat-content">{render_chat_ui()}</div>
            </div>
        </div>
        """, height=600)

def render_chat_ui():
    # Session
    if "chat_log" not in st.session_state:
        st.session_state.chat_log = []

    output = ""
    for entry in st.session_state.chat_log:
        output += f"<b>You:</b> {entry['user']}<br><b>Assistant:</b> {entry['assistant']}<hr>"

    prompt = st.text_input("Ask something...", key="assistant_input")
    if prompt:
        try:
            reply = safe_generate(prompt, system_msg=ASSISTANT_SYSTEM_PROMPT)
            st.session_state.chat_log.append({
                "user": prompt,
                "assistant": reply
            })
            log_assistant_interaction(get_user_id(), get_tenant_id(), prompt, reply)
            st.experimental_rerun()
        except Exception as e:
            reply = "❌ Sorry, something went wrong."
            logger.error(redact_log(f"❌ Assistant failed: {e}"))

    return output
