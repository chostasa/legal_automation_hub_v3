def render_chat_modal():
    if "show_assistant" not in st.session_state:
        st.session_state.show_assistant = False

    # === Floating chat bubble button (Streamlit native)
    chat_col = st.columns([1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    with chat_col[0]:
        st.markdown(
            """
            <style>
            .assistant-button {
                position: fixed;
                bottom: 25px;
                left: 25px;
                background-color: #0A1D3B;
                color: white;
                border: none;
                border-radius: 50%;
                width: 55px;
                height: 55px;
                font-size: 24px;
                text-align: center;
                z-index: 9999;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        if st.button("💬", key="toggle_assistant", help="Toggle Legal Automation Assistant"):
            st.session_state.show_assistant = not st.session_state.show_assistant

    # === Render Assistant Modal
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
