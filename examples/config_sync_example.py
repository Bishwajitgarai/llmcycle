import asyncio
from llmcycle import LLMCycle
from llmcycle.client import ConfigSource

async def main():
    print("🌍 Initializing LLMCycle with Global Redis Config Synchronization...")
    print("This allows multiple worker nodes to pull routes, groups, and fallbacks centrally!")
    
    # Normally you'd need a running Redis server at the specified URL.
    # If it fails to connect, it will log a warning and fall back gracefully.
    try:
        client = LLMCycle(
            config_source=ConfigSource.REDIS,
            redis_url="redis://localhost:6379/0",
            config_prefix="prod_"
        )
        
        print("\n✅ Successfully connected ConfigLoader!")
        print("Checking groups dynamically loaded from Redis...")
        groups = client.router.groups.list_all()
        print(f"Loaded Groups: {groups}")
        
    except Exception as e:
        print(f"\n⚠️  Could not connect to Redis: {e}")
        print("Make sure you have a Redis server running on localhost:6379 for this example.")

if __name__ == "__main__":
    asyncio.run(main())
