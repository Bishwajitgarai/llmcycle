import asyncio
import os
from llmcycle import LLMCycle

# ==========================================
# PRODUCTION "ALL AUTO" CONFIGURATION
# ==========================================
# This example demonstrates how to set up LLMCycle so your
# application code NEVER has to know about models, retries,
# fallbacks, or logging. It is 100% "auto".

# 1. Initialize the client globally
client = LLMCycle(
    auto_trim_context=True,
    storage="sqlite://llmcycle.db" # Auto-saves requests/costs to SQLite
)

async def setup():
    """Run this once at application startup."""
    print("⚙️ Configuring routing rules...")
    
    # Create a default production group with built-in fallbacks
    await client.router.groups.add(
        group_id="default_production_router",
        models=["anthropic/claude-3-5-sonnet", "openai/gpt-4o", "gemini/gemini-1.5-pro"]
    )
    print("✅ System setup complete. 'default_production_router' is ready.\n")

# ==========================================
# THE MAGIC "ALL AUTO" WRAPPER
# ==========================================
async def auto_complete(prompt: str):
    """
    Your application uses this generic function everywhere.
    It never passes a model. It automatically routes through
    the default production group.
    """
    try:
        response = await client.complete(
            group="default_production_router", 
            prompt=prompt
        )
        return response
    except Exception as e:
        print(f"❌ CRITICAL ERROR: All fallback models failed. Reason: {e}")
        return None

# ==========================================
# APPLICATION CODE
# ==========================================
async def main():
    print("🚀 Initializing Production System...")
    await setup()
    
    # Notice how clean the app code is! No models passed, no error handling required here.
    queries = [
        "What is the capital of France?",
        "Explain quantum computing in one sentence."
    ]
    
    for query in queries:
        print(f"Processing query: '{query}'")
        
        # 100% AUTO CALL
        response = await auto_complete(query)
        
        if response:
            print(f"✅ Success! Answered by: {response.model}")
            print(f"Response: {response.content}\n")

if __name__ == "__main__":
    asyncio.run(main())
