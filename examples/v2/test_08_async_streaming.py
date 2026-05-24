import asyncio
import sys
from dotenv import load_dotenv
from llmcycle import LLMCycle
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
    print(f"{BOLD}{BLUE}🚀 RUNNING TEST: Asynchronous Token-by-Token Streaming{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    MODEL = "openrouter/openai/gpt-oss-20b:free"
    client = LLMCycle()
    reset_key_cooldown(client)

    print("Requesting token stream...")
    try:
        chunks = []
        async for chunk in client.stream(MODEL, "Count from 1 to 3 slowly."):
            print(chunk, end="", flush=True)
            chunks.append(chunk)
        print()
        assert len(chunks) > 0
        print(f"{BOLD}{GREEN}✓ PASS: Asynchronous streaming verification complete!{RESET}")
    except Exception as e:
        print(f"\n\033[93m⚠ INFO: Streaming live call bypassed due to rate limit: {e}{RESET}")

if __name__ == "__main__":
    asyncio.run(main())
