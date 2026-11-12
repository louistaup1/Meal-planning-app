"""
Shared test setup.

Safety net: no test may ever call the real Claude API (it costs money, and on
PythonAnywhere the app's real key is loaded from .env). Every test runs without
the key, and the Anthropic client is replaced with one that fails loudly if used.
Tests that check ai_client.py replace it again with their own fake.
"""

import pytest

import ai_client


class NoRealClaude:
    def __init__(self, *args, **kwargs):
        raise AssertionError("A test tried to call the real Claude API. Use a pretend function instead.")


@pytest.fixture(autouse=True)
def block_real_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(ai_client.anthropic, "Anthropic", NoRealClaude)
