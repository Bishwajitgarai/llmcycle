"""
Unit tests for the Intent-Based Semantic Router.
"""
import pytest
from llmcycle.core.semantic import SemanticRouter

def test_semantic_routing_rules():
    rules = {
        "complex_reasoning": [r"explain", r"why", r"how", r"prove", r"solve", r"analyze"],
        "data_extraction": [r"json", r"extract", r"parse", r"regex", r"csv", r"table"],
        "simple_chat": []
    }
    routes = {
        "complex_reasoning": "openai/gpt-4o",
        "data_extraction": "groq/llama-3.1-70b",
        "simple_chat": "openai/gpt-4o-mini"
    }

    router = SemanticRouter(rules=rules, routes=routes, default_intent="simple_chat")

    # Verify complex reasoning matches
    assert router.classify("Explain the theory of relativity") == "complex_reasoning"
    assert router.route("Explain the theory of relativity") == "openai/gpt-4o"

    # Verify data extraction matches
    assert router.classify("Extract the phone numbers as a json object") == "data_extraction"
    assert router.route("Extract the phone numbers as a json object") == "groq/llama-3.1-70b"

    # Verify fallback matches default
    assert router.classify("Hi there, what is up?") == "simple_chat"
    assert router.route("Hi there, what is up?") == "openai/gpt-4o-mini"


def test_semantic_routing_custom_classifier():
    rules = {"simple_chat": []}
    routes = {"vip_intent": "openai/gpt-4o", "simple_chat": "openai/gpt-4o-mini"}

    def custom_classifier(prompt: str) -> str:
        if "premium" in prompt.lower():
            return "vip_intent"
        return "simple_chat"

    router = SemanticRouter(
        rules=rules, 
        routes=routes, 
        default_intent="simple_chat", 
        custom_classifier=custom_classifier
    )

    assert router.route("Hello premium user!") == "openai/gpt-4o"
    assert router.route("Hello ordinary user!") == "openai/gpt-4o-mini"
