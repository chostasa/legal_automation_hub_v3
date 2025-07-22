import os
import pytest
from config import get_env

def test_get_env_returns_value(monkeypatch):
    monkeypatch.setenv("MY_TEST_KEY", "foo")
    assert get_env("MY_TEST_KEY") == "foo"

def test_get_env_raises_if_missing(monkeypatch):
    monkeypatch.delenv("SOME_MISSING_KEY", raising=False)
    with pytest.raises(Exception):
        get_env("SOME_MISSING_KEY")
