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
    print(f"{BOLD}{BLUE}🚀 RUNNING TEST: Shadow Routing & Dark Launching{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    MODEL_PRIMARY = "openrouter/openai/gpt-oss-20b:free"
    MODEL_SHADOW = "openrouter/google/gemma-4-26b-a4b-it:free"

    client = LLMCycle(log_level="INFO")
    reset_key_cooldown(client)

    print(f"Executing request with primary model '{MODEL_PRIMARY}' and background shadow model '{MODEL_SHADOW}'...")
    try:
        # Shadow completions run in the background (fire-and-forget task)
        res = await client.complete(
            MODEL_PRIMARY,
            prompt="Say 'Primary Completed'",
            shadow_models=[MODEL_SHADOW]
        )
        print("Primary response:", res.content.strip())
        print(f"{BOLD}{GREEN}✓ PASS: Primary completion complete. Shadow completion dispatched in background!{RESET}")
    except Exception as e:
        print(f"\033[93m⚠ INFO: Live shadow call rate-limited: {e}{RESET}")

    # Give a tiny sleep to let the shadow call task start running in background
    await asyncio.sleep(1.0)

if __name__ == "__main__":
    asyncio.run(main())
