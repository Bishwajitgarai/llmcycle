import asyncio
from typing import List
from pydantic import BaseModel, Field

from llmcycle import LLMCycle
from llmcycle.schema import RoutingStrategy

# =========================================================================
# THE FULL SDK SHOWCASE
# =========================================================================
# This example initializes LLMCycle with almost EVERY feature activated.
# It acts as a master reference for all capabilities.
# =========================================================================

# 1. INITIALIZE WITH ALL FEATURES
client = LLMCycle(
    # Core Resiliency
    auto_trim_context=True,         # Truncate messages exceeding context window
    strategy=RoutingStrategy.PRIORITY, # Default routing strategy
    max_cost_usd=50.0,              # Stop completely if cost exceeds $50.00
    
    # Network & Storage
    proxy="http://your.proxy:8080", # All requests route through this proxy
    storage="sqlite://full_sdk.db", # Log all requests, responses, and costs
    
    # Caching Layer
    cache=True,                     # Exact-match prompt caching
    semantic_cache=True,            # Similarity-based caching (bypasses LLM for similar prompts)
    
    # Safety & Rate Limits
    guardrail=True,                 # Anonymize PII (emails, SSNs) before sending
    injection_guard=True,           # Block malicious jailbreak attempts
    rate_limits={"openai/gpt-4o": {"requests_per_minute": 500}}, # Client-side throttling
    
    # Telemetry tags applied to all requests
    session_id="sdk_showcase_run",
    user_id="user_admin",
    team_id="core_team"
)

# 2. STRUCTURED OUTPUT SCHEMA
class UserProfile(BaseModel):
    name: str = Field(description="The full name of the user")
    age: int = Field(description="The user's age")
    skills: List[str] = Field(description="List of technical skills")

# 3. TOOL / FUNCTION CALLING DEFINITION
async def get_weather(location: str) -> str:
    """Get the current weather for a specific location."""
    # In reality, you'd call an external API here
    if "London" in location:
        return "Raining, 12°C"
    return "Sunny, 25°C"

async def setup():
    print("⚙️ Initializing Advanced Routing...")
    
    # Define a high-speed group
    await client.router.groups.add(
        group_id="speed_cluster",
        models=["groq/llama-3.1-8b-instant", "openai/gpt-4o-mini"]
    )
    
    # Define fallbacks for our heavy model
    await client.router.fallbacks.add(
        primary_model="anthropic/claude-3-5-sonnet",
        fallback_models=["openai/gpt-4o", "gemini/gemini-1.5-pro"]
    )

async def run_showcase():
    print("\n--- 1. BASIC COMPLETION WITH CACHING ---")
    # The first time hits the API. The second time (if cache_ttl is set) hits the cache.
    res1 = await client.complete(
        group="speed_cluster",
        prompt="What is the speed of sound?",
        cache_ttl=3600 # Cache for 1 hour
    )
    print(f"Standard Response [{res1.model}]: {res1.content.strip()}")

    print("\n--- 2. STRUCTURED JSON OUTPUT ---")
    # Forces the LLM to return valid JSON matching the Pydantic schema
    res2 = await client.complete_structured(
        model="openai/gpt-4o-mini",
        prompt="Extract info: Jane Doe is a 28 year old Python and React developer.",
        response_model=UserProfile
    )
    print(f"Structured Response [{res2.model}]: {res2.parsed_data}")

    print("\n--- 3. FUNCTION/TOOL CALLING ---")
    # Automatically provides the tool to the LLM, executes it, and returns the final answer
    res3 = await client.complete_with_tools(
        model="openai/gpt-4o-mini",
        prompt="What is the weather like in London right now?",
        tools=[get_weather]
    )
    print(f"Tool-Assisted Response [{res3.model}]: {res3.content.strip()}")

    print("\n--- 4. BATCH PROCESSING ---")
    # Run multiple prompts concurrently
    res4_batch = await client.complete_batch(
        model="openai/gpt-4o-mini",
        prompts=["Explain RAG in one sentence.", "Explain LoRA in one sentence."],
        concurrency=2
    )
    print("Batch Responses:")
    for i, res in enumerate(res4_batch):
        print(f"  {i+1}: {res.content.strip()}")

    print("\n--- 5. ASYNC STREAMING ---")
    # Stream the response chunk by chunk
    print(f"Streaming from 'anthropic/claude-3-5-sonnet' (with fallbacks active):")
    async for chunk in client.stream(
        model="anthropic/claude-3-5-sonnet",
        prompt="Write a very short haiku about coding."
    ):
        print(chunk, end="", flush=True)
    print("\n")

async def main():
    print("==========================================")
    print("      LLMCYCLE MASTER SDK SHOWCASE        ")
    print("==========================================\n")
    
    await setup()
    
    try:
        await run_showcase()
    except Exception as e:
        print(f"\n❌ Error during showcase: {e}")
        
    print("\n💾 All requests, telemetry, and costs have been logged to full_sdk.db.")
    cost_summary = client.get_cost_summary()
    print(f"💰 Session Cost: ${cost_summary['total_cost_usd']:.6f} / Budget: ${cost_summary['budget_usd']:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
