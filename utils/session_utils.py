import streamlit as st
import uuid
import os

def get_session_id() -> str:
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    return st.session_state["session_id"]

def get_session_temp_dir(base_dir: str = "temp") -> str:
    session_id = get_session_id()
    path = os.path.join(base_dir, session_id)
    os.makedirs(path, exist_ok=True)
    return path
