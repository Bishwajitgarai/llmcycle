"""
Unit tests for PII and Secrets Guardrails.
"""
import pytest
from llmcycle.core.guardrail import GuardrailManager, calculate_entropy

def test_entropy_calculator():
    assert calculate_entropy("") == 0.0
    # High entropy string
    h = "sk-proj-83fHj2kKls9aPq1wZ4yT2xR"
    # Low entropy string
    l = "aaaaaaaaaaaa"
    assert calculate_entropy(h) > calculate_entropy(l)


def test_guardrail_mask_and_unmask():
    guard = GuardrailManager()

    prompt = (
        "Hello, my SSN is 123-45-6789, credit card: 1111-2222-3333-4444. "
        "Reach me at bobby@gmail.com on IP 192.168.1.1. "
        "Also my token is sk-proj-aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV."
    )

    masked = guard.mask_prompt(prompt)
    
    # Assert none of the sensitive values are visible in the masked prompt
    assert "123-45-6789" not in masked
    assert "1111-2222-3333-4444" not in masked
    assert "bobby@gmail.com" not in masked
    assert "192.168.1.1" not in masked
    assert "sk-proj-aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV" not in masked

    # Assert placeholders exist
    assert "[SSN_1]" in masked or "[SSN_" in masked
    assert "[CREDIT_CARD_" in masked
    assert "[EMAIL_" in masked
    assert "[IP_ADDRESS_" in masked
    assert "[SECRET_KEY_" in masked

    # Simulate model response that echoes some placeholders
    response = (
        "Sure, I recorded your details: [SSN_1], credit card: [CREDIT_CARD_2], "
        "email: [EMAIL_3], IP: [IP_ADDRESS_4], token: [SECRET_KEY_5]."
    )

    unmasked = guard.unmask_response(response)

    # Assert all original values are perfectly restored
    assert "123-45-6789" in unmasked
    assert "1111-2222-3333-4444" in unmasked
    assert "bobby@gmail.com" in unmasked
    assert "192.168.1.1" in unmasked
    assert "sk-proj-aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV" in unmasked
