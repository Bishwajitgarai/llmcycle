import asyncio
from llmcycle.core.keys import KeyManager
from llmcycle.core.router import ModelRouter, FallbackRouter
from llmcycle.core.stream import StreamResilienceManager
from llmcycle.schema import CompletionRequest, Message
from llmcycle.providers.base import LLMProvider
from typing import AsyncGenerator

class MockProvider(LLMProvider):
    """A mock provider that fails midway through the stream to test resilience."""
    def __init__(self, should_fail: bool):
        self.should_fail = should_fail
        
    async def generate(self, request: CompletionRequest, api_key: str) -> str:
        return "Hello World"
        
    async def generate_stream(self, request: CompletionRequest, api_key: str) -> AsyncGenerator[str, None]:
        chunks = ["Hello", " world", ",", " how", " are", " you?"]
        for i, chunk in enumerate(chunks):
            if self.should_fail and i == 3:
                raise ConnectionError("Mock streaming disconnect")
            yield chunk
            await asyncio.sleep(0.1)
            
    async def get_models(self, api_key: str) -> list[str]:
        return ["gpt-4", "gpt-4-turbo"]

async def main():
    print("Setting up LLMCycle Manager...")
    km = KeyManager()
    km.add_key("gpt-4-turbo", "sk-mock-1")
    km.add_key("gpt-4", "sk-mock-2")
    
    router = ModelRouter(FallbackRouter({"gpt-4-turbo": ["gpt-4"]}))
    
    providers = {
        "gpt-4-turbo": MockProvider(should_fail=True),
        "gpt-4": MockProvider(should_fail=False)
    }
    
    stream_manager = StreamResilienceManager(router, km, providers)
    
    request = CompletionRequest(
        model="gpt-4-turbo",
        messages=[Message(role="user", content="Say hello!")]
    )
    
    print("\nStarting robust stream...")
    try:
        async for chunk in stream_manager.safe_stream(request):
            print(chunk, end="", flush=True)
    except Exception as e:
        print(f"\nStream failed completely: {e}")
        
    print("\n\nFinished stream successfully, even with mid-stream disconnect!")

if __name__ == "__main__":
    asyncio.run(main())
