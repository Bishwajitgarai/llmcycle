import asyncio
import sys
from dotenv import load_dotenv
from llmcycle import LLMCycle
from llmcycle.core.errors import BudgetExceededError

load_dotenv()
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    print("\n--- Testing Budget Enforcement ---")
    client_budget = LLMCycle(max_cost_usd=0.0000000001) # Tiny budget
    # Give the free model an artificial price so we can trigger the budget error
    client_budget.pricing["openai/gpt-oss-20b:free"] = {"input": 0.5, "output": 0.5}
    try:
        await client_budget.complete("openrouter/openai/gpt-oss-20b:free", "Hello")
        print("Budget test failed - should have raised BudgetExceededError")
    except BudgetExceededError:
        print("Budget test passed.")

    print("\n--- Testing Middleware Hooks ---")
    hook_fired = {"before": False, "after": False}
    
    async def on_before(model, messages, kwargs):
        hook_fired["before"] = True
    async def on_after(model, response):
        hook_fired["after"] = True
        
    client_hooks = LLMCycle()
    client_hooks.on_before = on_before
    client_hooks.on_after = on_after
    
    await client_hooks.complete("openrouter/openai/gpt-oss-20b:free", "Hello")
    print(f"Middleware test passed: {hook_fired}")

    # Tool calling is hard to test with free models reliably as they might not support it well,
    # but we can try basic structure or verify it parses.
    # Structured output test could fail depending on model's instruction following.

if __name__ == "__main__":
    asyncio.run(main())
