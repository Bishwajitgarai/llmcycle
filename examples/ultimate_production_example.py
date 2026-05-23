import asyncio
import os
from llmcycle import LLMCycle

# ==========================================
# ULTIMATE PRODUCTION CONFIGURATION
# ==========================================
# This example demonstrates an enterprise-grade setup combining:
# - Proxy settings
# - Automatic context window trimming
# - Automatic database storage & cost tracking
# - Advanced fallback strategies and grouping
# - Graceful error handling
# ==========================================

# 1. INITIALIZE CLIENT WITH GLOBAL SETTINGS
# In production, initialize this once and use it everywhere.
client = LLMCycle(
    # Truncate conversation automatically if it exceeds the model's context window
    auto_trim_context=True,
    
    # Save all prompts, responses, and cost calculations locally to SQLite
    storage="sqlite://production_logs.db",
    
    # Optional: Route traffic through a corporate proxy
    # proxy="http://corporate.proxy.server:8080" 
)

async def setup_routing_rules():
    print("⚙️ Configuring routing rules and fallbacks...")
    
    # 2. CREATE INTELLIGENT MODEL GROUPS
    # Combine your fastest, cheapest models into one logical group
    await client.router.groups.add(
        group_id="tier_1_fast",
        models=["groq/llama-3.1-8b-instant", "openai/gpt-4o-mini"]
    )
    
    # 3. CONFIGURE CASCADING FALLBACKS
    # If the main heavy model fails, fall back to other capable models.
    # LLMCycle handles the errors and tries the next one transparently.
    await client.router.fallbacks.add(
        primary_model="anthropic/claude-3-5-sonnet",
        fallback_models=["openai/gpt-4o", "gemini/gemini-1.5-pro"]
    )
    print("✅ Routing rules initialized successfully.")


async def process_task(task_name: str, prompt: str, model: str = None, group: str = None):
    """
    4. UNIVERSAL COMPLETION HANDLER
    A generic function that can be used anywhere in your application.
    Notice how clean it is - no error retry logic, no API key fetching, 
    no storage code!
    """
    print(f"\n🚀 Starting Task: '{task_name}'")
    if group:
        print(f"🎯 Target Group: {group}")
    else:
        print(f"🎯 Target Model: {model}")
    
    try:
        # LLMCycle handles everything beneath the surface
        if group:
            response = await client.complete(
                group=group,
                prompt=prompt,
                temperature=0.2
            )
        else:
            response = await client.complete(
                model=model,
                prompt=prompt,
                temperature=0.2
            )
        
        print(f"✅ Success! Actual model used: {response.model}")
        print(f"💰 Tokens Used: {response.usage.total_tokens} | Cost: ${response.cost_usd:.6f}")
        print(f"📝 Response: {response.content.strip()[:100]}...")
        
    except Exception as e:
        # This only triggers if ALL fallbacks and retries fail
        print(f"❌ CRITICAL ERROR: All models failed for '{task_name}'.")
        print(f"   Reason: {e}")


async def main():
    print("==========================================")
    print("   LLMCYCLE ENTERPRISE PRODUCTION DEMO    ")
    print("==========================================\n")
    
    # Run setup once at startup
    await setup_routing_rules()
    
    # Task A: Use our 'tier_1_fast' group for a simple task
    await process_task(
        task_name="Summarize user input",
        group="tier_1_fast",
        prompt="Explain the difference between sync and async programming in 2 sentences."
    )
    
    # Task B: Use our heavy model with configured fallbacks for a complex task
    await process_task(
        task_name="Generate complex architecture",
        model="anthropic/claude-3-5-sonnet",
        prompt="Design a high-level architecture for a distributed rate-limiting service."
    )
    
    print("\n💾 Notice: All requests, tokens, and costs have been automatically saved to production_logs.db!")

if __name__ == "__main__":
    asyncio.run(main())
