"""
LLMCycle - Production-Grade All-in-One Universal LLM Router
============================================================
Auto multi-key rotation, intelligent error handling, streaming resilience,
agentic tool loops, structured output, prompt caching, budget enforcement,
and persistent storage — all in one library.
"""
from .client import LLMCycle
from .schema import CompletionRequest, Message, CompletionResponse, StreamChunk
from .core.keys import KeyManager, KeyStatus
from .core.router import ModelRouter, RoutingStrategy
from .core.errors import (
    LLMCycleError,
    RateLimitError,
    AuthenticationError,
    ProviderError,
    AllProvidersFailedError,
    StreamInterruptedError,
    MaxToolCallsExceededError,
    BudgetExceededError,
    ContextWindowError,
    StructuredOutputError,
    QuotaExceededError,
    ContentPolicyError,
)

__all__ = [
    # Client
    "LLMCycle",
    # Schema
    "CompletionRequest", "Message", "CompletionResponse", "StreamChunk",
    # Key management
    "KeyManager", "KeyStatus",
    # Routing
    "ModelRouter", "RoutingStrategy",
    # Errors
    "LLMCycleError",
    "RateLimitError",
    "AuthenticationError",
    "ProviderError",
    "AllProvidersFailedError",
    "StreamInterruptedError",
    "MaxToolCallsExceededError",
    "BudgetExceededError",
    "ContextWindowError",
    "StructuredOutputError",
    "QuotaExceededError",
    "ContentPolicyError",
]

__version__ = "0.1.6"
