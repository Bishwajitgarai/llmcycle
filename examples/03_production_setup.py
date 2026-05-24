"""
LLMCycle — Production Setup (Plug & Run)
==========================================
The "set it and forget it" pattern for production apps.

Declare everything once. Your entire application just calls `llm.complete(...)`.
No models, no retries, no storage code scattered across your codebase.

Setup:
    OPENAI_API_KEYS=sk-key1,sk-key2   # multi-key → auto-rotated
    ANTHROPIC_API_KEYS=sk-ant-...
    GROQ_API_KEYS=gsk_...
"""
import asyncio
from llmcycle import LLMCycle
from llmcycle.schema import RoutingStrategy

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Configure everything once, globally.
# ─────────────────────────────────────────────────────────────────────────────
llm = LLMCycle(
    # Routing
    strategy=RoutingStrategy.PRIORITY,

    # Safety & Quality
    auto_trim_context=True,   # Silently trims messages if they exceed context window
    guardrail=True,           # Masks PII (emails, keys) before sending, unmasks after
    injection_guard=True,     # Blocks prompt injection / jailbreak attempts

    # Cost control
    max_cost_usd=10.00,       # Hard stop if session cost exceeds $10.00

    # Observability — every request auto-logged with tokens, latency, cost
    storage="sqlite://llmcycle_production.db",

    # Telemetry tags stamped on every request
    session_id="app-session",
    team_id="backend-team",
)

async def setup():
    """Call this once when your application starts."""
    # Fallbacks: if primary fails, try backups silently
    await llm.router.fallbacks.add(
        primary_model="anthropic/claude-3-5-sonnet",
        fallback_models=["openai/gpt-4o", "gemini/gemini-1.5-pro"]
    )
    # Groups: define fast/cheap pool for non-critical tasks
    await llm.router.groups.add(
        group_id="fast",
        models=["groq/llama-3.1-8b-instant", "openai/gpt-4o-mini"]
    )

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Use `llm` anywhere in your application.
# No models, no API keys, no retry logic — just the prompt.
# ─────────────────────────────────────────────────────────────────────────────

async def summarize(text: str) -> str:
    """Simple task → use the fast, cheap group."""
    response = await llm.complete(
        group="fast",
        prompt=f"Summarize this in one sentence: {text}"
    )
    return response.content

async def analyze(text: str) -> str:
    """Complex task → use the smart model with fallbacks."""
    response = await llm.complete(
        model="anthropic/claude-3-5-sonnet",
        prompt=f"Analyze and explain the key insights from: {text}"
    )
    return response.content

async def main():
    # Boot once
    await setup()

    # Use everywhere — it just works
    summary = await summarize("LLMCycle is an enterprise LLM router with zero mandatory dependencies.")
    print(f"Summary: {summary}")

    analysis = await analyze("The global AI market is growing at 37% CAGR, driven by LLM adoption.")
    print(f"Analysis: {analysis}")

    # Show cost summary
    cost = llm.get_cost_summary()
    print(f"\nSession cost: ${cost['total_cost_usd']:.6f} / Budget: ${cost['budget_usd']:.2f}")

if __name__ == "__main__":
    asyncio.run(main())
