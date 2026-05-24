"""
LLMCycle — Getting Started
===========================
The simplest possible example. Just set your API keys in a .env file and go.

.env file:
    OPENAI_API_KEYS=sk-...
    GROQ_API_KEYS=gsk_...
"""
import asyncio
from llmcycle import LLMCycle

async def main():
    # Plug it in. LLMCycle auto-discovers your keys from .env.
    client = LLMCycle()

    # Basic completion
    response = await client.complete(
        model="openai/gpt-4o-mini",
        prompt="What is LLM routing? Answer in one sentence."
    )
    print(f"[{response.model}]: {response.content}")

    # Streaming
    print("\nStreaming response:")
    async for chunk in client.stream(
        model="openai/gpt-4o-mini",
        prompt="Write a haiku about software reliability."
    ):
        print(chunk, end="", flush=True)
    print()

if __name__ == "__main__":
    asyncio.run(main())
