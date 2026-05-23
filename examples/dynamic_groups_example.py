import asyncio
from llmcycle import LLMCycle
from llmcycle.core.router import RoutingStrategy

async def main():
    print("🚀 Initializing LLMCycle with Dynamic Groups...")
    # Initialize the client with some initial groups and fallback strategy
    client = LLMCycle(
        strategy=RoutingStrategy.ACTIVE_FIRST,
        groups={
            "tier_1": [
                "openai/gpt-4o",
                "anthropic/claude-3-5-sonnet",
                "deepseek/deepseek-chat"
            ],
            "tier_2": [
                "groq/llama-3.1-70b",
                "openai/gpt-4o-mini"
            ]
        }
    )

    print("\n📋 Current configured groups:")
    print(client.router.groups.list_all())

    print("\n1️⃣  Testing routing with the 'tier_2' group...")
    try:
        # Request completion by passing a group name instead of a model
        # LLMCycle will attempt to use groq/llama-3.1-70b, then automatically fallback to openai/gpt-4o-mini
        response = await client.complete(group="tier_2", prompt="What is 2+2? Reply briefly.")
        print(f"✅ Success! Routed to: {response.model}")
        print(f"🤖 Response: {response.content}")
    except Exception as e:
        print(f"⚠️  Error: {e} (Did you set your API keys?)")

    print("\n2️⃣  Modifying groups dynamically at runtime...")
    # Add a new group on the fly without restarting the application
    client.router.groups.set("cost_saver", ["groq/llama-3.1-8b", "deepseek/deepseek-chat"])
    print("Added 'cost_saver' group.")
    print(client.router.groups.list_all())

    print("\n3️⃣  Routing with primary model + fallback group...")
    try:
        # Request a specific model but fallback to the 'cost_saver' group if it fails
        response = await client.complete(model="openai/gpt-4", group="cost_saver", prompt="Explain gravity in one sentence.")
        print(f"✅ Success! Routed to: {response.model}")
        print(f"🤖 Response: {response.content}")
    except Exception as e:
        print(f"⚠️  Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
