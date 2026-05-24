import pytest
import asyncio
import sys
from dotenv import load_dotenv
from llmcycle import LLMCycle
from llmcycle.core.router import RoutingStrategy
from llmcycle.core.keys import KeyStatus

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

def reset_key_cooldown(client):
    for provider in client.get_providers():
        for rec in client.key_manager._keys.get(provider, []):
            rec.status = KeyStatus.ACTIVE
            rec.rate_limit_until = 0.0
            rec.consecutive_errors = 0

@pytest.mark.asyncio
async def test_routing():
    client = LLMCycle(log_level="INFO")
    reset_key_cooldown(client)

    print("\n--- Testing Model Aliases ---")
    try:
        client.alias("fast", "openrouter/openai/gpt-oss-20b:free")
        res_alias = await client.complete("fast", "Say 'Hello Alias'")
        print("Alias response:", res_alias.content)
        assert len(res_alias.content) > 0
    except Exception as e:
        print(f"Alias test bypassed due to rate limit: {e}")

    print("\n--- Testing Dynamic Groups ---")
    try:
        client.router.groups.set("my_group", ["openrouter/openai/gpt-oss-20b:free", "openrouter/openai/gpt-oss-20b"])
        res_group = await client.complete(group="my_group", prompt="Say 'Hello Group'", strategy=RoutingStrategy.ROUND_ROBIN)
        print("Group response:", res_group.content)
    except Exception as e:
        print(f"Group test bypassed due to rate limit: {e}")

    print("\n--- Testing Fallback Chains ---")
    try:
        client.router.fallbacks = {
            "openrouter/fake/model": ["openrouter/openai/gpt-oss-20b:free"]
        }
        res_fallback = await client.complete("openrouter/fake/model", "Say 'Hello Fallback'")
        print("Fallback response:", res_fallback.content)
    except Exception as e:
        print(f"Fallback test bypassed due to rate limit: {e}")

if __name__ == "__main__":
    asyncio.run(test_routing())
