from typing import Tuple, Dict

def parse_model(model_str: str) -> Tuple[str, str]:
    """
    Parse a model string into (provider, model).
    
    Examples:
        "openai/gpt-4o" -> ("openai", "gpt-4o")
        "gpt-4o"        -> ("openai", "gpt-4o")  (if logic allows, but defaults to ("gpt-4o", "gpt-4o") without default_provider logic)
        "groq"          -> ("groq", "groq")
    """
    if "/" in model_str:
        parts = model_str.split("/", 1)
        return parts[0].lower(), parts[1]
    # Bare model name — return as-is; caller resolves provider
    return model_str.lower(), model_str

# ─── Pricing registry (USD per 1K tokens) ─────────────────────────────────────
# Override / extend via client.pricing["gpt-4o"] = {"input": 0.005, "output": 0.015}
DEFAULT_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o":              {"input": 0.005,   "output": 0.015},
    "gpt-4o-mini":         {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo":         {"input": 0.01,    "output": 0.03},
    "gpt-3.5-turbo":       {"input": 0.0005,  "output": 0.0015},
    "claude-3-opus":       {"input": 0.015,   "output": 0.075},
    "claude-3-sonnet":     {"input": 0.003,   "output": 0.015},
    "claude-3-haiku":      {"input": 0.00025, "output": 0.00125},
    "deepseek-chat":       {"input": 0.00014, "output": 0.00028},
    "llama-3.1-70b":       {"input": 0.00059, "output": 0.00079},
    "llama-3.1-8b":        {"input": 0.00005, "output": 0.00008},
    "mixtral-8x7b":        {"input": 0.00024, "output": 0.00024},
    "gemma-7b-it":         {"input": 0.00007, "output": 0.00007},
}

# ─── Context window registry (tokens) ─────────────────────────────────────────
DEFAULT_CONTEXT_WINDOWS: Dict[str, int] = {
    "gpt-4o":              128_000,
    "gpt-4o-mini":         128_000,
    "gpt-4-turbo":         128_000,
    "gpt-3.5-turbo":       16_385,
    "claude-3-opus":       200_000,
    "claude-3-sonnet":     200_000,
    "claude-3-haiku":      200_000,
    "deepseek-chat":       64_000,
    "llama-3.1-70b":       128_000,
    "llama-3.1-8b":        128_000,
    "mixtral-8x7b":        32_768,
    "gemma-7b-it":         8_192,
}
