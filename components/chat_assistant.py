def render_chat_modal():
    if "show_assistant" not in st.session_state:
        st.session_state.show_assistant = False

    # Inject floating bubble HTML
    st.markdown("""
        <style>
        .chat-button {
            position: fixed;
            bottom: 25px;
            left: 25px;
            z-index: 9999;
            width: 65px;
            height: 65px;
            border-radius: 50%;
            background-color: #0A1D3B;
            color: white;
            font-size: 30px;
            text-align: center;
            line-height: 65px;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.3);
            cursor: pointer;
        }
        </style>
        <div class="chat-button" onclick="toggleAssistant()">💬</div>
        <script>
        function toggleAssistant() {
            const frame = window.parent.document.querySelector('iframe');
            frame.contentWindow.postMessage({ type: 'streamlit:rerun' }, '*');
            fetch('/_stcore/_broadcast', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ event: 'toggle_chat_state' })
            });
        }
        </script>
    """, unsafe_allow_html=True)

    # Fallback toggle logic (for Streamlit rerun)
    toggle = st.experimental_get_query_params().get("chat", [None])[0]
    if toggle == "show":
        st.session_state.show_assistant = True
    elif toggle == "hide":
        st.session_state.show_assistant = False

    # Render chat modal
    if st.session_state.get("show_assistant", False):
        with st.container():
            st.markdown("""
                <div style="
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
                ">
            """, unsafe_allow_html=True)

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
