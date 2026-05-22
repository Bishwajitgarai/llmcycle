"""
Unit tests for Canary and Weighted Routing strategies.
"""
import pytest
from llmcycle.core.router import ModelRouter, RoutingStrategy

def test_canary_routing_distribution():
    # Configure weighted routing: 80% to gpt-4o-mini, 20% to llama-3.1-70b
    fallbacks = {
        "hybrid-model": {
            "openai/gpt-4o-mini": 0.80,
            "groq/llama-3.1-70b": 0.20,
        }
    }
    router = ModelRouter(fallbacks=fallbacks, strategy=RoutingStrategy.CANARY)

    counts = {"openai": 0, "groq": 0}
    
    # Sample 500 times to check the routing distribution
    for _ in range(500):
        route = router.get_route("hybrid-model")
        primary_provider, primary_model = route[0]
        counts[primary_provider] += 1

    # Verify that both are selected
    assert counts["openai"] > 0
    assert counts["groq"] > 0
    
    # Statistical expectation: openai ~400, groq ~100
    # Allow safe boundaries (300-475 for openai, 25-200 for groq)
    assert 300 <= counts["openai"] <= 475
    assert 25 <= counts["groq"] <= 200


def test_canary_routing_fallback_order():
    fallbacks = {
        "hybrid-model": {
            "openai/gpt-4o-mini": 0.70,
            "groq/llama-3.1-70b": 0.20,
            "anthropic/claude-3": 0.10,
        }
    }
    router = ModelRouter(fallbacks=fallbacks, strategy=RoutingStrategy.WEIGHTED)

    route = router.get_route("hybrid-model")
    
    # First candidate must be one of the three
    assert route[0][0] in ("openai", "groq", "anthropic")
    assert len(route) == 3

    # The order of the remaining candidates must be sorted descending by weight
    if route[0][0] == "openai":
        # remaining: groq (0.20), anthropic (0.10)
        assert route[1] == ("groq", "llama-3.1-70b")
        assert route[2] == ("anthropic", "claude-3")
    elif route[0][0] == "groq":
        # remaining: openai (0.70), anthropic (0.10)
        assert route[1] == ("openai", "gpt-4o-mini")
        assert route[2] == ("anthropic", "claude-3")
    else:
        # remaining: openai (0.70), groq (0.20)
        assert route[1] == ("openai", "gpt-4o-mini")
        assert route[2] == ("groq", "llama-3.1-70b")
