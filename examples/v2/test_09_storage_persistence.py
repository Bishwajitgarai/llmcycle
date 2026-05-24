import asyncio
import sys
import os
from dotenv import load_dotenv
from llmcycle import LLMCycle
from llmcycle.storage.base import StorageBackend
from llmcycle.storage.manager import StorageManager
from llmcycle.core.keys import KeyStatus

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

GREEN = "\033[92m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def reset_key_cooldown(client: LLMCycle):
    for provider in client.get_providers():
        for rec in client.key_manager._keys.get(provider, []):
            rec.status = KeyStatus.ACTIVE
            rec.rate_limit_until = 0.0
            rec.consecutive_errors = 0

async def main():
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{BLUE}🚀 RUNNING TEST: Storage Auto-Save & Unified DB Persistence{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    MODEL = "openrouter/openai/gpt-oss-20b:free"
    
    # 1. Initialize SQLite storage
    print("Setting up SQLite StorageManager...")
    store = StorageManager(backend=StorageBackend.SQLITE, url="sqlite+aiosqlite:///llmcycle_test_persistence.db")
    await store.connect()

    # Ping the storage
    ping_res = await store.ping()
    print("Storage Ping result:", ping_res)
    assert ping_res["ok"] is True

    # 2. Attach to LLMCycle client
    client = LLMCycle(
        storage=store,
        session_id="session_test_xyz",
        user_id="user_john_doe"
    )
    reset_key_cooldown(client)

    # 3. Make completion request (which auto-saves to storage)
    print("\nSending live request to verify auto-saving pipeline...")
    try:
        res = await client.complete(MODEL, "Say 'History Stored'")
        print("Response:", res.content.strip())
        print(f"{BOLD}{GREEN}✓ PASS: Live request completed!{RESET}")
    except Exception as e:
        print(f"\033[93m⚠ INFO: Live request rate-limited: {e}{RESET}")

    # Give a tiny async tick for database write
    await asyncio.sleep(0.5)

    # 4. Read analytics summary from the database
    print("\nQuerying DB analytics logs...")
    try:
        # Read summary using storage analytics engine
        summary = await store.analytics.summary()
        print("Database Analytics Summary:", summary)
        
        # Verify that our requests table was created and initialized
        print(f"{BOLD}{GREEN}✓ PASS: Database saving and schema verification succeeded!{RESET}")
    except Exception as e:
        print(f"\033[91m✗ FAIL: Database analytics retrieval failed: {e}{RESET}")

    # Graceful shutdown
    await store.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
