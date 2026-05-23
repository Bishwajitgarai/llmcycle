from typing import Tuple

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
