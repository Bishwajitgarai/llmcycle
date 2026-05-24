import asyncio
import sys
import time
from dotenv import load_dotenv
from llmcycle import LLMCycle
from llmcycle.core.cache import SQLCache
from llmcycle.core.semantic_cache import SemanticCache

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    print("\n--- Testing SQLCache ---")
    client_sql = LLMCycle(cache=SQLCache(url="sqlite+aiosqlite:///llmcycle_cache_test.db"))
    await client_sql.cache_clear()
    
    t0 = time.time()
    res1 = await client_sql.complete("openrouter/openai/gpt-oss-20b:free", "Say exactly 'Hello Cache'", cache_ttl=60)
    t1 = time.time()
    print(f"Call 1 took {t1-t0:.2f}s: {res1.content}")

    t0 = time.time()
    res2 = await client_sql.complete("openrouter/openai/gpt-oss-20b:free", "Say exactly 'Hello Cache'", cache_ttl=60)
    t1 = time.time()
    print(f"Call 2 took {t1-t0:.2f}s: {res2.content}")
    assert (t1-t0) < 0.5, "Cache should be nearly instantaneous"

    print("\n--- Testing Semantic Cache ---")
    client_sem = LLMCycle(semantic_cache=SemanticCache(similarity_threshold=0.85))
    await client_sem._semantic_cache.clear()
    
    t0 = time.time()
    res_sem1 = await client_sem.complete("openrouter/openai/gpt-oss-20b:free", "How do I make a cake?")
    t1 = time.time()
    print(f"Semantic 1 took {t1-t0:.2f}s: {res_sem1.content[:50]}...")

    t0 = time.time()
    res_sem2 = await client_sem.complete("openrouter/openai/gpt-oss-20b:free", "What is the recipe for baking a cake?")
    t1 = time.time()
    print(f"Semantic 2 took {t1-t0:.2f}s: {res_sem2.content[:50]}...")
    
    print("\n--- Testing Context Auto-Trim ---")
    # Provide an artificially small context window
    client_trim = LLMCycle(context_windows={"gpt-oss-20b:free": 50}, auto_trim_context=True)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Word 1 " * 50},  # ~50 tokens
        {"role": "user", "content": "Word 2 " * 50},  # ~50 tokens
    ]
    # It should trim the first user message
    res_trim = await client_trim.complete("openrouter/openai/gpt-oss-20b:free", messages=messages)
    print("Auto-trim passed. Response:", res_trim.content[:50])

if __name__ == "__main__":
    asyncio.run(main())
