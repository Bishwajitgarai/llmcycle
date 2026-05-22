import os
from dotenv import load_dotenv
from llmcycle.core.keys import KeyManager
from llmcycle.core.router import ModelRouter, FallbackRouter
from llmcycle.core.stream import StreamResilienceManager
from llmcycle.providers.openai_compatible import OpenAICompatibleProvider

# Massive default registry
PROVIDER_BASE_URLS = {
    "OPENAI": "https://api.openai.com/v1",
    "DEEPSEEK": "https://api.deepseek.com/v1",
    "ANTHROPIC": "https://api.anthropic.com/v1",
    "TOGETHER": "https://api.together.xyz/v1",
    "GROQ": "https://api.groq.com/openai/v1",
    "MISTRAL": "https://api.mistral.ai/v1",
    "PERPLEXITY": "https://api.perplexity.ai",
    "ANYSCALE": "https://api.endpoints.anyscale.com/v1",
    "FIREWORKS": "https://api.fireworks.ai/inference/v1",
    "COHERE": "https://api.cohere.com/v1",
    "DATABRICKS": "https://serving.api.databricks.com/serving-endpoints",
    "HUGGINGFACE": "https://api-inference.huggingface.co/models",
}

class LLMCycle:
    """Main entrypoint for LLMCycle with Universal Provider Support."""
    
    def __init__(self, env_path: str = ".env", custom_fallbacks: dict = None):
        load_dotenv(env_path)
        
        self.key_manager = KeyManager()
        self.providers = {}
        
        # Auto-discover
        self._auto_load_keys()
        
        # Setup Routing Strategy
        fallbacks = custom_fallbacks or {}
        self.router = ModelRouter(FallbackRouter(fallbacks))
        self.stream_manager = StreamResilienceManager(self.router, self.key_manager, self.providers)

    def _auto_load_keys(self):
        """Finds any env var ending with _API_KEYS and universally registers the provider."""
        for key, val in os.environ.items():
            if key.endswith("_API_KEYS"):
                provider_name = key.replace("_API_KEYS", "").upper()
                keys = [k.strip() for k in val.split(",") if k.strip()]
                
                if not keys:
                    continue
                    
                # 1. Check if user explicitly defined a BASE URL for this provider
                # 2. Check the massive default registry
                # 3. Fallback: Assume a standard OpenAI compatible format
                base_url = os.environ.get(f"{provider_name}_BASE_URL")
                if not base_url:
                    base_url = PROVIDER_BASE_URLS.get(provider_name, f"https://api.{provider_name.lower()}.com/v1")
                
                if base_url:
                    self.providers[provider_name.lower()] = OpenAICompatibleProvider(base_url)
                    for k in keys:
                        self.key_manager.add_key(provider_name.lower(), k)

    def get_available_providers(self) -> list[str]:
        return list(self.providers.keys())

    async def get_provider_models(self, provider_name: str) -> list[str]:
        p_name = provider_name.lower()
        if p_name not in self.providers:
            return []
        key = self.key_manager.get_next_key(p_name)
        if not key:
            return []
        return await self.providers[p_name].get_models(key)
