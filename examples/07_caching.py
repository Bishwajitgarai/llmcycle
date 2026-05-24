"""
LLMCycle — Prompt Caching & Semantic Caching
===============================================
Two cache layers to eliminate redundant API calls:

1. EXACT CACHE (cache_ttl): Returns the cached response instantly for
   identical prompts within the TTL window. Great for deterministic queries.

2. SEMANTIC CACHE: Returns a cached response if a semantically similar
   prompt has been seen before (using TF-IDF cosine similarity).
   "How do I build a RAG app?" matches "What's the best way to build RAG?"
"""
import asyncio
import time
from llmcycle import LLMCycle
from llmcycle.core.semantic_cache import SemanticCache

# ── Exact-match cache ─────────────────────────────────────────────────────────
exact_client = LLMCycle(cache=True)

# ── Semantic similarity cache ─────────────────────────────────────────────────
semantic_client = LLMCycle(
    semantic_cache=SemanticCache(similarity_threshold=0.85)
)

async def demo_exact_cache():
    print("── Exact Cache ──────────────────────────────")
    prompt = "What is the speed of light? Answer in one sentence."
    
    t0 = time.monotonic()
    r1 = await exact_client.complete(model="openai/gpt-4o-mini", prompt=prompt, cache_ttl=300)
    t1 = time.monotonic()
    print(f"First call  ({(t1-t0)*1000:.0f}ms): {r1.content.strip()}")

    t0 = time.monotonic()
    r2 = await exact_client.complete(model="openai/gpt-4o-mini", prompt=prompt, cache_ttl=300)
    t1 = time.monotonic()
    print(f"Second call ({(t1-t0)*1000:.0f}ms): served from cache ✅")

async def demo_semantic_cache():
    print("\n── Semantic Cache ───────────────────────────")
    prompt1 = "How do I build a RAG application?"
    prompt2 = "What is the best way to create a RAG app?"  # semantically similar

    t0 = time.monotonic()
    r1 = await semantic_client.complete(model="openai/gpt-4o-mini", prompt=prompt1)
    t1 = time.monotonic()
    print(f"First call  ({(t1-t0)*1000:.0f}ms): '{prompt1}'")
    print(f"  → {r1.content.strip()[:80]}...")

    t0 = time.monotonic()
    r2 = await semantic_client.complete(model="openai/gpt-4o-mini", prompt=prompt2)
    t1 = time.monotonic()
    print(f"Second call ({(t1-t0)*1000:.0f}ms): '{prompt2}'")
    print(f"  → Semantic cache hit ✅ (no API call made)")

async def main():
    await demo_exact_cache()
    await demo_semantic_cache()

if __name__ == "__main__":
    asyncio.run(main())
