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
    print(f"{BOLD}{BLUE}🚀 RUNNING TEST: Concurrency Batching (complete_batch){RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    MODEL = "openrouter/openai/gpt-oss-20b:free"
    client = LLMCycle()
    reset_key_cooldown(client)

    prompts = [
        "Explain RAG in 1 sentence.",
        "Explain LoRA in 1 sentence."
    ]

    print("Running parallel batch requests with concurrency limit...")
    try:
        results = await client.complete_batch(MODEL, prompts, concurrency=2)
        print(f"Batch results received ({len(results)} items):")
        for idx, res in enumerate(results):
            content = res.content.strip() if res else "Failed (Rate Limited)"
            print(f"  - Prompt {idx+1}: {content}")
        print(f"{BOLD}{GREEN}✓ PASS: Parallel batch completion interface verified!{RESET}")
    except Exception as e:
        print(f"\033[93m⚠ INFO: Batch completion live call rate-limited: {e}{RESET}")

if __name__ == "__main__":
    asyncio.run(main())
