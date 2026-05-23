import asyncio
from llmcycle import LLMCycle

async def main():
    print("🚀 Initializing LLMCycle for High-Concurrency Batch Processing...")
    
    client = LLMCycle()
    
    # Let's say we have a large list of tasks to process concurrently.
    tasks = [
        "What is the capital of France?",
        "Explain quantum computing in one sentence.",
        "What is the airspeed velocity of an unladen swallow?",
        "Write a haiku about Python.",
        "Translate 'Hello, world!' to Spanish."
    ]
    
    print(f"\n📦 Submitting {len(tasks)} prompts in parallel...")
    
    # `complete_batch` handles parallel concurrency internally,
    # respecting the rate limits of your configured providers.
    try:
        results = await client.complete_batch(
            model="openai/gpt-4o-mini",
            prompts=tasks,
            concurrency=5  # How many to run at the same time
        )
        
        print("\n✅ Batch Processing Complete!\n")
        
        for idx, (prompt, response) in enumerate(zip(tasks, results)):
            print(f"--- Task {idx+1} ---")
            print(f"Q: {prompt}")
            if isinstance(response, Exception):
                print(f"A: ⚠️  Error: {response}")
            else:
                print(f"A: {response.content.strip()}")
            print("-" * 20)
            
    except Exception as e:
        print(f"⚠️  Error executing batch: {e}")

if __name__ == "__main__":
    asyncio.run(main())
