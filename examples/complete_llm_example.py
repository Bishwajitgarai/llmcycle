import asyncio
import os
from typing import List
from pydantic import BaseModel, Field

# Import all core and storage components of LLMCycle
from llmcycle import LLMCycle, RoutingStrategy
from llmcycle.storage import StorageBackend, StorageManager
from llmcycle.storage.models import User, Session

# Define a Pydantic model for structured outputs
class UserProfile(BaseModel):
    name: str = Field(description="The person's name")
    skills: List[str] = Field(description="List of core software engineering skills")
    experience_years: int = Field(description="Number of years of experience in system design/AI")

async def run_complete_example():
    print("=" * 70)
    print("       🚀 LLMCycle Production-Grade Complete End-to-End Example 🚀")
    print("=" * 70)

    # ---------------------------------------------------------------------------
    # 1. SETUP THE STORAGE LAYER
    # ---------------------------------------------------------------------------
    # Using SQLite as a zero-config persistent storage layer. 
    # This automatically tracks all completions, sessions, users, and latencies.
    print("\n📦 Connecting to SQLite Storage Backend...")
    store = StorageManager(
        backend=StorageBackend.SQLITE,
        table_prefix="demo_"  # Stored in tables starting with demo_
    )
    await store.connect()
    
    # Ping storage to verify connection health
    ping_res = await store.ping()
    print(f"✅ Storage connected successfully! Ping latency: {ping_res['latency_ms']:.2f}ms")

    # ---------------------------------------------------------------------------
    # 2. CREATE USER & SESSION
    # ---------------------------------------------------------------------------
    print("\n👤 Creating user and session for analytics tracking...")
    user = await store.create_user(User(
        username="dev_bishwajit",
        email="bishwajit@example.com",
        role="developer"
    ))
    
    session = await store.create_session(Session(
        user_id=user.id,
        model="openai/gpt-4o-mini"
    ))
    print(f"✅ User and Session initialized. Session ID: {session.id}")

    # ---------------------------------------------------------------------------
    # 3. INITIALIZE THE LLMCYCLE CLIENT
    # ---------------------------------------------------------------------------
    # We configure full routing strategies, prompt caching, token budgets,
    # and extensive fallback routing chains.
    print("\n🤖 Initializing LLMCycle Client...")
    client = LLMCycle(
        env_path=".env",                  # Auto-discovers key patterns from your .env
        storage=store,                    # Link client to storage for automatic logging
        session_id=session.id,            # Group all requests under this session
        user_id=user.id,                  # Stamped on all requests
        strategy=RoutingStrategy.PRIORITY,# Route strategy: PRIORITY, ROUND_ROBIN, or LOWEST_LATENCY
        
        # Fallbacks: If deepseek fails, try groq, then openai. Works at model level too!
        fallbacks={
            "deepseek": ["groq", "openai"],
            "deepseek/deepseek-chat": ["groq/llama-3.1-70b-versatile", "openai/gpt-4o-mini"]
        }
    )

    # ---------------------------------------------------------------------------
    # 4. VIEW LOADED PROVIDERS & KEY HEALTH
    # ---------------------------------------------------------------------------
    providers = client.get_providers()
    print(f"✅ LLMCycle dynamically discovered these active providers from env:")
    for p in providers:
        stats = client.key_manager.key_count(p)
        print(f"   • [{p.upper()}]: {stats['active']}/{stats['total']} keys healthy")

    # ---------------------------------------------------------------------------
    # 5. RESILIENT NON-STREAMING COMPLETION
    # ---------------------------------------------------------------------------
    print("\n💬 1. Executing non-streaming completion (with automatic logs)...")
    try:
        response = await client.complete(
            model="openai/gpt-4o-mini",
            prompt="Explain the core benefit of key rotation in 15 words.",
            temperature=0.7,
            max_tokens=100
        )
        print(f"   [Response Content]: {response.content.strip()}")
        print(f"   [Metrics]: Routed via {response.provider} | Latency: {response.latency_ms:.0f}ms")
    except Exception as e:
        print(f"   ❌ Request failed: {e}")

    # ---------------------------------------------------------------------------
    # 6. RESILIENT STREAMING (AUTO-FAILOVER IN ACTION)
    # ---------------------------------------------------------------------------
    print("\n🌊 2. Executing resilient streaming...")
    try:
        print("   [Stream Output]: ", end="", flush=True)
        # If your primary endpoint fails mid-stream, llmcycle automatically
        # catches the context and continues seamlessly using your backup provider.
        async for chunk in client.stream(
            model="openai/gpt-4o-mini",
            prompt="Write a 3-line poem about infinite key rotation."
        ):
            print(chunk, end="", flush=True)
        print()
    except Exception as e:
        print(f"\n   ❌ Streaming failed: {e}")

    # ---------------------------------------------------------------------------
    # 7. STRUCTURED OUTPUT (PYDANTIC EXTRACTION)
    # ---------------------------------------------------------------------------
    print("\n🧩 3. Extracting structured Pydantic output...")
    try:
        profile: UserProfile = await client.structured_complete(
            model="openai/gpt-4o-mini",
            prompt="Bishwajit is a Senior Backend Engineer with 7 years of system design experience. Core skills include Python, FastAPI, and Kubernetes.",
            response_model=UserProfile
        )
        print(f"   [Pydantic Result]: Name={profile.name}, Exp={profile.experience_years} years")
        print(f"   [Skills Extracted]: {', '.join(profile.skills)}")
    except Exception as e:
        print(f"   ❌ Structured extraction failed: {e}")

    # ---------------------------------------------------------------------------
    # 8. ANALYTICS & MONITORING
    # ---------------------------------------------------------------------------
    print("\n📈 4. Pulling production analytics from the SQLite storage manager...")
    summary = await store.analytics.summary()
    print("   =========================================")
    print("            LLMCYCLE PERFORMANCE SUMMARY     ")
    print("   =========================================")
    print(f"   • Total Logged Requests: {summary.get('total_requests', 0)}")
    print(f"   • Total Tokens Consumed: {summary.get('total_tokens', 0)}")
    print(f"   • Average Latency      : {summary.get('avg_latency_ms', 0.0):.2f}ms")
    print(f"   • P95 Latency          : {summary.get('p95_latency_ms', 0.0):.2f}ms")
    print(f"   • Error Rate           : {summary.get('error_rate', 0.0) * 100:.2f}%")
    print(f"   • Cooldown/Fallback Rate: {summary.get('fallback_rate', 0.0) * 100:.2f}%")
    print("   =========================================")

    # Breakdown per model
    by_model = await store.analytics.by_model()
    print("\n📊 Model Usage Breakdown:")
    for model_stat in by_model:
        print(f"   • Model: {model_stat['model']} | Requests: {model_stat['requests']} | Tokens: {model_stat['tokens']}")

    # ---------------------------------------------------------------------------
    # 9. DISCONNECT & CLEANUP
    # ---------------------------------------------------------------------------
    print("\n🔌 Disconnecting from storage...")
    await store.disconnect()
    print("🏁 Done! Launch 'llmcycle ui' in your terminal to see this data beautifully visualized on the dashboard!")

if __name__ == "__main__":
    # Ensure there is a dummy .env or keys loaded for testing
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write("OPENAI_API_KEYS=sk-fake-key-for-local-demo\n")
            f.write("LLMCYCLE_USER_ADMIN=admin\n")
            f.write("LLMCYCLE_USER_ADMIN_PAASWORD=admin\n")
            
    asyncio.run(run_complete_example())
