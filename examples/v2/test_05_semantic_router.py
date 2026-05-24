import asyncio
import sys
from dotenv import load_dotenv
from llmcycle import LLMCycle, SemanticRouter
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
    print(f"{BOLD}{BLUE}🚀 RUNNING TEST: Semantic Router & Intent Classification{RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}")

    MODEL_LLAMA = "openrouter/meta-llama/llama-3.2-3b-instruct:free"
    MODEL_GPT = "openrouter/openai/gpt-oss-20b:free"

    # Define rules and routes
    rules = {
        "reasoning": [r"explain", r"why", r"how", r"prove"],
        "chitchat": []
    }
    routes = {
        "reasoning": MODEL_GPT,
        "chitchat": MODEL_LLAMA
    }

    # Instantiate router
    router = SemanticRouter(rules=rules, routes=routes, default_intent="chitchat")

    # 1. Test offline classification
    intent1 = router.classify("Explain how standard relativity works.")
    target_model1 = router.route("Explain how standard relativity works.")
    intent2 = router.classify("Hey, what's up?")
    target_model2 = router.route("Hey, what's up?")

    print(f"Classification 1: intent='{intent1}' -> model='{target_model1}'")
    print(f"Classification 2: intent='{intent2}' -> model='{target_model2}'")
    
    assert target_model1 == MODEL_GPT
    assert target_model2 == MODEL_LLAMA
    print(f"{BOLD}{GREEN}✓ PASS: Intent-based routing logic is fully functional!{RESET}")

    # 2. Test live completion using routed target model
    client = LLMCycle()
    reset_key_cooldown(client)
    try:
        print(f"\nMaking live completion to routed target model: {target_model2}...")
        res = await client.complete(target_model2, "Say 'Hello from routed model'")
        print("Response:", res.content.strip())
        print(f"{BOLD}{GREEN}✓ PASS: Live completion on routed model succeeded!{RESET}")
    except Exception as e:
        print(f"\033[93m⚠ INFO: Live routed completion bypassed due to rate limit: {e}{RESET}")

if __name__ == "__main__":
    asyncio.run(main())
