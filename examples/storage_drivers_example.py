import asyncio
from llmcycle import LLMCycle
from llmcycle.storage import StorageManager, StorageBackend
from llmcycle.drivers.sql import SQLDriver

async def main():
    print("🚀 Initializing Storage Manager with a custom SQLDriver...")
    
    # 1. Create a dynamic SQL driver (Using in-memory SQLite for demonstration)
    driver = SQLDriver(url="sqlite+aiosqlite:///:memory:")
    
    # 2. Wrap it with the unified StorageManager
    store = StorageManager(StorageBackend.SQLITE, driver=driver, table_prefix="demo_")
    
    # Connect and initialize the database tables
    await store.connect()
    print("✅ Database connected and tables created!")

    # 3. Pass the storage engine into LLMCycle
    client = LLMCycle(
        storage=store,
        session_id="user_session_123",
        user_id="user_john_doe"
    )

    print("\n💬 Sending a chat request... (It will be automatically saved to DB!)")
    try:
        response = await client.complete("openai/gpt-4o-mini", "Why is the sky blue? Answer in 10 words.")
        print(f"🤖 Response: {response.content}")
        
        print("\n🔍 Fetching saved request from the database...")
        # Check if it was saved using the raw driver layer
        async with store.driver.get_session() as session:
            # We can run arbitrary queries or use the builtin store methods
            history = await store.get_history("user_session_123")
            print(f"📚 Retrieved {len(history)} messages from DB History:")
            for msg in history:
                print(f"  [{msg.role.upper()}]: {msg.content}")
                
    except Exception as e:
        print(f"⚠️  API Error: {e} (Did you set OPENAI_API_KEYS?)")

    # Cleanup database connection
    await store.close()
    print("\n🔌 Disconnected from DB.")

if __name__ == "__main__":
    asyncio.run(main())
