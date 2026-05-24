"""
LLMCycle — Storage & Analytics
=================================
Auto-log every request to SQLite (or Redis, MongoDB, PostgreSQL).
Then query analytics: total requests, tokens, latency, cost breakdown.

Supports:
  - SQLite (zero config)
  - PostgreSQL
  - Redis
  - MongoDB

.env:
    OPENAI_API_KEYS=sk-...
"""
import asyncio
from llmcycle import LLMCycle
from llmcycle.storage import StorageManager, StorageBackend

async def main():
    # ── 1. Connect to storage ─────────────────────────────────────────────
    store = StorageManager(backend=StorageBackend.SQLITE)
    await store.connect()

    # ── 2. Initialize client with storage attached ────────────────────────
    # Every call to complete(), stream(), etc. is auto-logged.
    client = LLMCycle(
        storage=store,
        session_id="my-app-session",
        user_id="user-123",
    )

    # ── 3. Make some requests (they auto-log) ─────────────────────────────
    prompts = [
        "Explain RAG in 5 words.",
        "Explain LoRA in 5 words.",
        "Explain RLHF in 5 words.",
    ]
    responses = await client.complete_batch(
        model="openai/gpt-4o-mini",
        prompts=prompts,
        concurrency=3,
    )
    for prompt, resp in zip(prompts, responses):
        if resp:
            print(f"Q: {prompt}\nA: {resp.content.strip()}\n")

    # ── 4. Pull analytics ─────────────────────────────────────────────────
    summary = await store.analytics.summary()
    print("=" * 50)
    print("       SESSION ANALYTICS")
    print("=" * 50)
    print(f"  Total Requests : {summary.get('total_requests', 0)}")
    print(f"  Total Tokens   : {summary.get('total_tokens', 0)}")
    print(f"  Avg Latency    : {summary.get('avg_latency_ms', 0):.1f}ms")
    print(f"  Error Rate     : {summary.get('error_rate', 0) * 100:.1f}%")
    print("=" * 50)

    await store.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
