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
# New market features
from .core.injection import InjectionGuard, InjectionBlockedError
from .core.prompts import PromptRegistry, PromptVersion
from .core.semantic_cache import SemanticCache
from .core.secrets import (
    SecretLoader, EnvSecretLoader,
    AWSSecretLoader, GCPSecretLoader, VaultSecretLoader,
    SecretNotFoundError, SecretLoadError,
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
    # Injection guard
    "InjectionGuard", "InjectionBlockedError",
    # Prompt registry
    "PromptRegistry", "PromptVersion",
    # Semantic cache
    "SemanticCache",
    # Secret loaders
    "SecretLoader", "EnvSecretLoader",
    "AWSSecretLoader", "GCPSecretLoader", "VaultSecretLoader",
    "SecretNotFoundError", "SecretLoadError",
]

__version__ = "0.2.0"
