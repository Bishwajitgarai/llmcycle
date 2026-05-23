import asyncio
import os
from llmcycle import LLMCycle

async def main():
    print("🚀 Initializing LLMCycle...")
    client = LLMCycle()
    
    # 1. Create a simple group with a few models
    # This group simply acts as an alias for a pool of models.
    await client.router.groups.add(
        group_id="my_fast_models",
        models=["groq/llama-3.1-8b-instant", "openai/gpt-4o-mini"]
    )
    
    print("\n✅ Group 'my_fast_models' created!")
    
    # 2. Use the group directly in a completion request!
    # LLMCycle will automatically try the models in the group.
    print("\n💬 Requesting completion using the group...")
    try:
        response = await client.complete(
            group="my_fast_models", 
            prompt="What is the speed of light? Keep it to one sentence."
        )
        print(f"\n✅ Success! Answered by: {response.model}")
        print(f"Response: {response.content}")
        
    except Exception as e:
        print(f"\n⚠️  Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
