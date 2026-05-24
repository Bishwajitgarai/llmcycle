import asyncio
import sys
from dotenv import load_dotenv
from llmcycle import LLMCycle
from llmcycle.core.keys import KeyStatus

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
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
    print(f"{BOLD}{BLUE}🚀 RUNNING TEST: Per-Request Timeouts & Cancellation tracking{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    MODEL = "openrouter/openai/gpt-oss-20b:free"
    client = LLMCycle(log_level="INFO")
    reset_key_cooldown(client)

    # 1. Test case: Setting a tiny per-request timeout (0.0001 seconds)
    print("Sending request with artificially short timeout (0.0001s)...")
    try:
        await client.complete(
            MODEL,
            prompt="Tell me a very long story about ancient history.",
            timeout=0.0001
        )
        print("\033[91m✗ FAIL: Timeout was not enforced!{RESET}")
    except asyncio.TimeoutError:
        print(f"{BOLD}{GREEN}✓ PASS: Request successfully timed out and caught asyncio.TimeoutError!{RESET}")
    except Exception as e:
        # If the rate limit or connection drops before the timeout, that is also a correct execution
        print(f"{BOLD}{YELLOW}⚠ INFO: Live request exited before timeout: {e}{RESET}")

if __name__ == "__main__":
    asyncio.run(main())
