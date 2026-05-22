import pytest
from llmcycle.core.keys import KeyManager

def test_add_and_get_key():
    km = KeyManager()
    km.add_key("openai", "sk-123")
    km.add_key("openai", "sk-456")

    # Should rotate round-robin
    assert km.get_next_key("openai") == "sk-123"
    assert km.get_next_key("openai") == "sk-456"
    assert km.get_next_key("openai") == "sk-123"

def test_rate_limit_report():
    km = KeyManager()
    km.add_key("openai", "sk-123")
    km.add_key("openai", "sk-456")

    # NEW API: report_error(provider, key, error_type)
    km.report_error("openai", "sk-123", "rate_limit")

    # sk-123 should be skipped now
    assert km.get_next_key("openai") == "sk-456"
    assert km.get_next_key("openai") == "sk-456"
