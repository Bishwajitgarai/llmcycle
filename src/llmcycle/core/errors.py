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


# Maps HTTP status codes to exception types
def classify_http_error(status_code: int, response_text: str, provider: str, model: str) -> LLMCycleError:
    """Factory: Convert an HTTP error into the correct LLMCycle exception."""
    text_lower = response_text.lower()

    if status_code == 401:
        return AuthenticationError(f"[{provider}] Auth failed (401): {response_text}", provider=provider, model=model, status_code=status_code)

    if status_code == 429:
        if any(w in text_lower for w in ("quota", "limit exceeded", "exhausted", "billing")):
            return QuotaExceededError(f"[{provider}] Quota exceeded (429): {response_text}", provider=provider, model=model, status_code=status_code)
        return RateLimitError(f"[{provider}] Rate limited (429): {response_text}", provider=provider, model=model, status_code=status_code)

    if status_code == 402:
        return QuotaExceededError(f"[{provider}] Payment required (402): {response_text}", provider=provider, model=model, status_code=status_code)

    if status_code == 400:
        if any(w in text_lower for w in ("content_policy", "safety", "harmful", "violat")):
            return ContentPolicyError(f"[{provider}] Content policy (400): {response_text}", provider=provider, model=model, status_code=status_code)
        return ProviderError(f"[{provider}] Bad request (400): {response_text}", provider=provider, model=model, status_code=status_code)

    # All other 4xx/5xx
    return ProviderError(f"[{provider}] HTTP {status_code}: {response_text[:200]}", provider=provider, model=model, status_code=status_code)
