import httpx
from typing import AsyncGenerator
from llmcycle.schema import CompletionRequest
from llmcycle.providers.base import LLMProvider

class OpenAICompatibleProvider(LLMProvider):
    """A generic provider for OpenAI-compatible APIs (OpenAI, DeepSeek, Together, etc)."""
    
    def __init__(self, base_url: str):
        # Ensure base_url ends with /v1 or whatever is passed
        self.base_url = base_url.rstrip('/')
        
    async def get_models(self, api_key: str) -> list[str]:
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/models", headers=headers, timeout=5.0)
                response.raise_for_status()
                data = response.json()
                if "data" in data:
                    return [model["id"] for model in data["data"]]
                return []
            except Exception as e:
                print(f"Failed to fetch models from {self.base_url}: {e}")
                return []

    async def generate(self, request: CompletionRequest, api_key: str) -> str:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            payload = request.model_dump(exclude_none=True)
            payload["stream"] = False
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=60.0)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def generate_stream(self, request: CompletionRequest, api_key: str) -> AsyncGenerator[str, None]:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            payload = request.model_dump(exclude_none=True)
            payload["stream"] = True
            
            async with client.stream("POST", f"{self.base_url}/chat/completions", headers=headers, json=payload) as response:
                response.raise_for_status()
                async for chunk in response.aiter_text():
                    # Simplified parsing of Server-Sent Events (SSE)
                    if chunk.startswith("data: "):
                        import json
                        data_str = chunk[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if data["choices"][0]["delta"].get("content"):
                                yield data["choices"][0]["delta"]["content"]
                        except json.JSONDecodeError:
                            pass
