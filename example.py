import asyncio
from llmcycle import LLMCycle
from llmcycle.core.router import RoutingStrategy

async def main():
    print("=" * 60)
    print("  LLMCycle - Production Example")
    print("=" * 60)

    # ─── 1. Init ────────────────────────────────────────────────
    # Auto-loads OPENAI_API_KEYS, DEEPSEEK_API_KEYS, GROQ_API_KEYS, etc. from .env
    client = LLMCycle(
        env_path=".env",
        fallbacks={
            # If deepseek fails or gets rate-limited → try groq, then openai
            "deepseek":                 ["groq", "openai"],
            "deepseek/deepseek-chat":   ["groq/llama-3.1-70b-versatile", "openai/gpt-4o-mini"],
        },
        strategy=RoutingStrategy.PRIORITY,
        log_level="INFO",
    )

    # ─── 2. List providers ───────────────────────────────────────
    providers = client.get_providers()
    print(f"\n✅ Loaded providers: {providers}")

    for p in providers:
        stats = client.key_manager.key_count(p)
        print(f"   [{p}] keys: {stats['active']}/{stats['total']} active")

    # ─── 3. Get models from a provider ──────────────────────────
    if providers:
        p = providers[0]
        print(f"\n📋 Fetching models for '{p}'...")
        models = await client.get_models(p)
        if models:
            print(f"   {models[:5]} ... ({len(models)} total)")
        else:
            print(f"   (Could not fetch models — check API key)")

    # ─── 4. Non-streaming completion ────────────────────────────
    if providers:
        print("\n💬 Non-streaming completion (with fallback routing)...")
        try:
            resp = await client.complete(
                model=f"{providers[0]}/gpt-4o-mini",
                prompt="Say 'Hello from LLMCycle!' in exactly 5 words.",
            )
            print(f"   [{resp.provider}] {resp.content} ({resp.latency_ms:.0f}ms)")
        except Exception as e:
            print(f"   Error: {e}")

    # ─── 5. Streaming completion ─────────────────────────────────
    if providers:
        print("\n🌊 Streaming completion (resilient mid-stream failover)...")
        try:
            print("   ", end="", flush=True)
            async for chunk in client.stream(
                model=f"{providers[0]}/gpt-4o-mini",
                prompt="Count from 1 to 5 with a short fact about each number.",
            ):
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            print(f"\n   Stream error: {e}")

    print("\n✅ Done.")

if __name__ == "__main__":
    asyncio.run(main())
