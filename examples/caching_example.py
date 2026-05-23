import asyncio
import time
from llmcycle import LLMCycle
from llmcycle.core.semantic_cache import SemanticCache

async def main():
    print("⚡ Initializing LLMCycle with Semantic & Exact Prompt Caching...")
    
    # Enable semantic caching (using TF-IDF / Cosine Similarity) with a threshold of 0.85
    client = LLMCycle(
        semantic_cache=SemanticCache(similarity_threshold=0.85)
    )

    queries = [
        "What are the primary colors?",                     # 1. First time (Cache Miss)
        "What are the primary colors?",                     # 2. Exact Match (Cache Hit)
        "Can you tell me what the primary colors are?"      # 3. Semantic Match (Cache Hit)
    ]

    for i, q in enumerate(queries, 1):
        print(f"\n💬 Query #{i}: '{q}'")
        
        start_time = time.time()
        try:
            # We must specify `cache_ttl` > 0 to enable caching for this specific request
            response = await client.complete("openai/gpt-4o-mini", prompt=q, cache_ttl=300)
            
            elapsed = time.time() - start_time
            
            # If the response was served from the cache, `response.cached` is True
            if getattr(response, "cached", False):
                print(f"🎯 CACHE HIT! Served in {elapsed:.3f} seconds.")
            else:
                print(f"🌐 CACHE MISS (Network Call). Served in {elapsed:.3f} seconds.")
                
            print(f"🤖 Response: {response.content}")
            
        except Exception as e:
            print(f"⚠️  Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
