import asyncio
from llmcycle import LLMCycle

async def main():
    print("💸 Initializing LLMCycle with Budgets and Rate Limits...")
    
    # Initialize the client with strict limits
    client = LLMCycle(
        # Hard cap: Reject requests if total spending exceeds $0.05
        max_cost_usd=0.05,
        
        # Rate Limits: Max 10 Requests Per Minute for OpenAI models
        rate_limits={
            "openai": {"rpm": 10, "tpm": 10000}
        }
    )

    print("\n📈 Sending queries and tracking costs...")
    
    for i in range(1, 4):
        print(f"\n💬 Query #{i}")
        try:
            response = await client.complete("openai/gpt-4o-mini", prompt="Say hello and tell me a short fact about space.")
            
            print(f"🤖 Response: {response.content}")
            print(f"💰 Cost for this request: ${response.cost_usd:.5f}")
            print(f"📊 Total Session Spending: ${client._total_cost_usd:.5f} / ${client.max_cost_usd}")
            
        except Exception as e:
            # If rate limit or budget is exceeded, an error is thrown before the network request is made
            print(f"⚠️  Blocked: {type(e).__name__} -> {e}")

if __name__ == "__main__":
    asyncio.run(main())
