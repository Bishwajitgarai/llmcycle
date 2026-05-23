from typing import Dict, List
PRIMARY_MODELS: Dict[str, List[str]] = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    "anthropic": ["claude-3-5-sonnet", "claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    "google": ["gemini-1.5-pro", "gemini-1.5-flash"],
    "deepseek": ["deepseek-chat", "deepseek-coder"],
    "groq": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
    "together": [
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "mistralai/Mixtral-8x7B-Instruct-v0.1"
    ],
    "ollama": ["llama3", "mistral", "phi3", "gemma"],
    "lm_studio": ["local-model"],
    "vllm": ["local-model"],
    "openrouter": ["meta-llama/llama-3.1-70b-instruct", "google/gemini-flash-1.5", "openai/gpt-4o-mini"],
}
