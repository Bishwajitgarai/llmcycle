"""
Custom exceptions for LLMCycle.
All errors map from HTTP status codes so the router knows exactly
what to do: retry, rotate key, skip provider, or give up.
"""

class LLMCycleError(Exception):
    """Base error for all LLMCycle exceptions."""
    def __init__(self, message: str, provider: str = "", model: str = "", status_code: int = 0):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.status_code = status_code

class RateLimitError(LLMCycleError):
    """429: Rate limit exceeded. Rotate key and retry."""
    pass

class AuthenticationError(LLMCycleError):
    """401: Invalid API key. Disable key permanently."""
    pass

class ProviderError(LLMCycleError):
    """400/500+: Provider-side error. Try next provider."""
    pass

class QuotaExceededError(LLMCycleError):
    """402/429 with quota message: Key quota exhausted. Rotate key."""
    pass

class ContentPolicyError(LLMCycleError):
    """400: Content policy violation. Do NOT retry - fail fast."""
    pass

class StreamInterruptedError(LLMCycleError):
    """Mid-stream disconnection. Contains partial text generated so far."""
    def __init__(self, message: str, partial_text: str = "", **kwargs):
        super().__init__(message, **kwargs)
        self.partial_text = partial_text

class AllProvidersFailedError(LLMCycleError):
    """Raised when every provider in the fallback chain fails."""
    def __init__(self, errors: list):
        msg = f"All {len(errors)} providers failed. Last error: {errors[-1]}"
        super().__init__(msg)
        self.errors = errors

class MaxToolCallsExceededError(LLMCycleError):
    """
    Raised when an agentic tool-calling loop exceeds max_tool_calls.

    Attributes:
        tool_call_count:   How many tool calls were executed before stopping.
        max_tool_calls:    The configured limit.
        partial_messages:  The message list accumulated so far.
    """
    def __init__(self, tool_call_count: int, max_tool_calls: int, partial_messages: list = None):
        super().__init__(
            f"Tool call loop exceeded limit: {tool_call_count}/{max_tool_calls} calls used."
        )
        self.tool_call_count = tool_call_count
        self.max_tool_calls = max_tool_calls
        self.partial_messages = partial_messages or []

class BudgetExceededError(LLMCycleError):
    """
    Raised when accumulated cost on a client exceeds max_cost_usd.

    Attributes:
        spent:  Total USD spent so far (tracked by storage).
        budget: Configured max_cost_usd limit.
    """
    def __init__(self, spent: float, budget: float):
        super().__init__(f"Budget exceeded: ${spent:.4f} spent of ${budget:.4f} limit.")
        self.spent = spent
        self.budget = budget

class ContextWindowError(LLMCycleError):
    """
    Raised when the prompt exceeds the model's context window
    and auto-truncation is disabled.

    Attributes:
        token_count:   Estimated token count of the prompt.
        context_limit: Model's maximum context window.
    """
    def __init__(self, token_count: int, context_limit: int, model: str = ""):
        super().__init__(
            f"Prompt has ~{token_count} tokens but model context is {context_limit} tokens.",
            model=model,
        )
        self.token_count = token_count
        self.context_limit = context_limit

class StructuredOutputError(LLMCycleError):
    """
    Raised when the LLM response cannot be parsed into the requested Pydantic schema.

    Attributes:
        raw_response: The raw text returned by the model.
    """
    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response


# ─── HTTP error classifier ────────────────────────────────────────────────────

def classify_http_error(
    status_code: int, response_text: str, provider: str, model: str
) -> LLMCycleError:
    """Factory: Convert an HTTP error into the correct LLMCycle exception."""
    text_lower = response_text.lower()

    if status_code == 401:
        return AuthenticationError(
            f"[{provider}] Auth failed (401): {response_text}",
            provider=provider, model=model, status_code=status_code,
        )
    if status_code == 429:
        if any(w in text_lower for w in ("quota", "limit exceeded", "exhausted", "billing")):
            return QuotaExceededError(
                f"[{provider}] Quota exceeded (429): {response_text}",
                provider=provider, model=model, status_code=status_code,
            )
        return RateLimitError(
            f"[{provider}] Rate limited (429): {response_text}",
            provider=provider, model=model, status_code=status_code,
        )
    if status_code == 402:
        return QuotaExceededError(
            f"[{provider}] Payment required (402): {response_text}",
            provider=provider, model=model, status_code=status_code,
        )
    if status_code == 400:
        if any(w in text_lower for w in ("content_policy", "safety", "harmful", "violat")):
            return ContentPolicyError(
                f"[{provider}] Content policy (400): {response_text}",
                provider=provider, model=model, status_code=status_code,
            )
        return ProviderError(
            f"[{provider}] Bad request (400): {response_text}",
            provider=provider, model=model, status_code=status_code,
        )
    return ProviderError(
        f"[{provider}] HTTP {status_code}: {response_text[:200]}",
        provider=provider, model=model, status_code=status_code,
    )
