import asyncio
import sys
from llmcycle import LLMCycle
from llmcycle.core.router import RoutingStrategy

async def main():
    print("🔁 Initializing LLMCycle with Stream Resilience Fallback...")
    
    # We define a strict fallback chain
    # If groq fails (or mid-stream cuts out), it will automatically and seamlessly
    # fail over to openai and resume the stream where it left off!
    client = LLMCycle(
        strategy=RoutingStrategy.PRIORITY,
        fallbacks={
            "primary_model": ["groq/llama-3.1-70b", "openai/gpt-4o-mini"]
        }
    )

    print("\n🌊 Starting resilient stream...")
    print("If Groq rate-limits you mid-sentence, LLMCycle will catch the exception,")
    print("switch to OpenAI, feed it the partial response, and seamlessly continue!\n")
    
    print("🤖 Response: ", end="", flush=True)
    
    try:
        # `safe_stream` automatically handles mid-stream disconnects and provider swaps!
        async for chunk in client.stream("primary_model", prompt="Write a 3-paragraph story about a robot learning to paint."):
            print(chunk, end="", flush=True)
            
    except Exception as e:
        print(f"\n\n⚠️  Stream completely failed across all fallbacks: {e}")
    else:
        print("\n\n✅ Stream completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
