"""
LLMCycle — Smart Fallbacks & Groups
======================================
This example shows the two core resilience features:

1. FALLBACKS: If primary model fails → automatically try backups.
2. GROUPS: Define a logical pool of models and route to the pool.

These are defined ONCE at startup. Your app code stays clean.
"""
import asyncio
from llmcycle import LLMCycle

# ── 1. Initialize once ───────────────────────────────────────────────────────
client = LLMCycle()

async def setup():
    """Called once at app startup."""
    
    # FALLBACKS: If claude fails, auto-try gpt-4o, then gemini
    await client.router.fallbacks.add(
        primary_model="anthropic/claude-3-5-sonnet",
        fallback_models=["openai/gpt-4o", "gemini/gemini-1.5-pro"]
    )
    
    # GROUPS: Create a pool of fast, cheap models under one alias
    await client.router.groups.add(
        group_id="fast",
        models=["groq/llama-3.1-8b-instant", "openai/gpt-4o-mini"]
    )

# ── 2. Use anywhere in your app ──────────────────────────────────────────────
async def main():
    await setup()
    
    # Use a group — LLMCycle picks the best available model from the pool
    response = await client.complete(
        group="fast",
        prompt="Explain load balancing in one sentence."
    )
    print(f"[{response.model}]: {response.content}")
    
    # Use a model with automatic fallbacks (configured above)
    response = await client.complete(
        model="anthropic/claude-3-5-sonnet",
        prompt="Explain API key rotation in one sentence."
    )
    print(f"[{response.model}]: {response.content}")

if __name__ == "__main__":
    asyncio.run(main())
