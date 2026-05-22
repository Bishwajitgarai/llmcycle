"""
LLMCycle - Production-Grade Universal LLM Router
=================================================
Auto multi-key rotation, intelligent error handling, streaming resilience,
and support for 50+ providers out-of-the-box.
"""
from .client import LLMCycle
from .schema import CompletionRequest, Message, CompletionResponse, StreamChunk
from .core.keys import KeyManager, KeyStatus
from .core.router import ModelRouter, RoutingStrategy
from .core.errors import (
    LLMCycleError, RateLimitError, AuthenticationError,
    ProviderError, AllProvidersFailedError, StreamInterruptedError,
)

__all__ = [
    "LLMCycle",
    "CompletionRequest", "Message", "CompletionResponse", "StreamChunk",
    "KeyManager", "KeyStatus",
    "ModelRouter", "RoutingStrategy",
    "LLMCycleError", "RateLimitError", "AuthenticationError",
    "ProviderError", "AllProvidersFailedError", "StreamInterruptedError",
]

__version__ = "0.1.2"
