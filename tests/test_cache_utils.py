import streamlit as st
from core import cache_utils

def test_set_get_clear_cache(monkeypatch):
    st.session_state.clear()
    cache_utils.set_cache("testkey", "value")
    assert cache_utils.get_cache("testkey") == "value"

    cache_utils.clear_caches()
    assert cache_utils.get_cache("testkey") is None
