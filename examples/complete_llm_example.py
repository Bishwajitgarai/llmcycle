import sys
import asyncio
import os
from typing import List
from pydantic import BaseModel, Field

# Support UTF-8 emoji printing on Windows console
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

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
    user = await store.get_user_by_username("dev_bishwajit")
    if not user:
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
        
        # Enterprise & Reliability settings
        cache=True,                       # Pluggable caching layer (InMemoryCache)
        rate_limits=True,                 # Client-side rate limiter (60 RPM / 40,000 TPM)
        guardrail=True,                   # Automatically masks PII and secrets on prompt, unmasks on response
        max_cost_usd=10.00,               # Enforce hard cost budget for this session
        auto_trim_context=True,           # Auto-truncate message history to fit model limits
        
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
    # 4.5. DYNAMIC LIVE MODEL DISCOVERY
    # ---------------------------------------------------------------------------
    print("\n📋 Dynamic Live Model Discovery...")
    try:
        live_models = await client.get_all_live_models()
        if not live_models:
            print("   • (No live models loaded)")
        else:
            for prov, models in live_models.items():
                print(f"   • [{prov.upper()}]: Found {len(models)} live models (e.g. {models[:3]}...)")
    except Exception as e:
        print(f"   ❌ Live models fetch failed: {e}")

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
    # 7. STRUCTURED OUTPUT (TOOL-CALLING MODE — DEFAULT)
    # ---------------------------------------------------------------------------
    print("\n🧩 3. Extracting structured Pydantic output (via tool-calling API)...")
    try:
        # DEFAULT mode: use_tool_format=True
        # LLMCycle converts the Pydantic schema into an OpenAI function definition
        # and forces the model to "call" it. Arguments arrive as pre-parsed JSON
        # — no markdown stripping, no regex heuristics, far more reliable.
        profile: UserProfile = await client.complete_structured(
            model="openai/gpt-4o-mini",
            prompt="Bishwajit is a Senior Backend Engineer with 7 years of system design experience. Core skills include Python, FastAPI, and Kubernetes.",
            schema=UserProfile,
            use_tool_format=True,   # ← default; set False for legacy JSON-prompt mode
        )
        print(f"   [Tool-call Result]: Name={profile.name}, Exp={profile.experience_years} years")
        print(f"   [Skills Extracted]: {', '.join(profile.skills)}")
    except Exception as e:
        print(f"   ❌ Structured extraction failed: {e}")

    # ---------------------------------------------------------------------------
    # 7.5. MULTIMODAL ATTACHMENTS (LOCAL & S3 BACKENDS)
    # ---------------------------------------------------------------------------
    print("\n📎 3.5. Sending prompt with multimodal attachments...")
    try:
        # Create a tiny dummy text document to attach
        temp_file = "demo_attachment.txt"
        with open(temp_file, "w") as f:
            f.write("System audit status: All operations nominal.")
            
        print(f"   [Attachments]: Sending query with local file '{temp_file}'...")
        response = await client.complete(
            model="openai/gpt-4o-mini",
            prompt="Analyze the attached system audit status and summarize in 5 words.",
            attachments=[temp_file]
        )
        print(f"   [Response Content]: {response.content.strip()}")
        
        # Clean up the demo file
        if os.path.exists(temp_file):
            os.remove(temp_file)
    except Exception as e:
        print(f"   ❌ Multimodal completion failed (requires active provider keys): {e}")

    # ---------------------------------------------------------------------------
    # 7.6. PLUGGABLE PROMPT CACHING (FAST TTL MEMORY/DB CACHE)
    # ---------------------------------------------------------------------------
    print("\n♻️ 3.6. Pluggable Prompt Caching in Action...")
    try:
        import time
        prompt = "What is the speed of light in vacuum? Respond in 5 words."
        print(f"   [First Call] Sending query to API (Cache-TTL: 60s)...")
        t0 = time.monotonic()
        response1 = await client.complete(
            model="openai/gpt-4o-mini",
            prompt=prompt,
            cache_ttl=60
        )
        latency1 = (time.monotonic() - t0) * 1000
        print(f"   [Response 1]: '{response1.content.strip()}' (Time: {latency1:.1f}ms)")

        print(f"   [Second Call] Sending identical query (served from cache)...")
        t1 = time.monotonic()
        response2 = await client.complete(
            model="openai/gpt-4o-mini",
            prompt=prompt,
            cache_ttl=60
        )
        latency2 = (time.monotonic() - t1) * 1000
        print(f"   [Response 2]: '{response2.content.strip()}' (Time: {latency2:.1f}ms) [Instant Cache Hit!]")
    except Exception as e:
        print(f"   ❌ Prompt caching failed: {e}")

    # ---------------------------------------------------------------------------
    # 7.7. PII & SECRETS GUARDRAIL (AUTOMATIC MASKING / UNMASKING)
    # ---------------------------------------------------------------------------
    print("\n🛡️ 3.7. PII & Secrets Guardrails in Action...")
    try:
        # Prompt contains an email address and an OpenAI API key (high-entropy secret key)
        raw_prompt = (
            "Summarize: My contact is bobby@gmail.com and my API key is "
            "sk-proj-aB1cD2eF3gH4iJ5kL6mN7oP8qR9sT0uV."
        )
        print("   [Raw Prompt]:", raw_prompt)
        
        # When guardrail=True, llmcycle automatically intercepts the prompt,
        # masks it to: "Summarize: My contact is [EMAIL_1] and my API key is [SECRET_KEY_1]"
        # and when the model replies, it automatically restores the original values!
        print("   [Guardrail Masking] Sending masked query to provider...")
        response = await client.complete(
            model="openai/gpt-4o-mini",
            prompt=raw_prompt
        )
        print(f"   [Unmasked Response Content]: {response.content.strip()}")
    except Exception as e:
        print(f"   ❌ Guardrail completion failed: {e}")

    # ---------------------------------------------------------------------------
    # 7.8. BUDGET ENFORCEMENT & CONTEXT WINDOW AUTO-TRIM
    # ---------------------------------------------------------------------------
    print("\n🚦 3.8. Cost Budget & Context Trimming Status...")
    print(f"   • Current Session Cost Tracker: {client._total_cost_usd:.6f} USD")
    print(f"   • Configured Session Budget limit: {client.max_cost_usd} USD")
    print(f"   • Context Window Auto-Trim is active: {client.auto_trim_context}")

    # ---------------------------------------------------------------------------
    # 7.9. INTENT-BASED SEMANTIC ROUTING
    # ---------------------------------------------------------------------------
    print("\n♻️ 3.9. Intent-Based Semantic Routing...")
    try:
        from llmcycle.core.semantic import SemanticRouter
        
        # Configure routing intents based on pattern keywords/regex
        rules = {
            "complex_reasoning": [r"explain", r"why", r"how", r"prove", r"solve", r"analyze"],
            "data_extraction": [r"json", r"extract", r"parse", r"regex", r"csv", r"table"],
            "simple_chat": [] # fallback intent if no rules match
        }
        
        # Map intents to target models
        routes = {
            "complex_reasoning": "openai/gpt-4o",
            "data_extraction": "groq/llama-3.1-70b-versatile",
            "simple_chat": "openai/gpt-4o-mini"
        }
        
        sem_router = SemanticRouter(rules=rules, routes=routes, default_intent="simple_chat")
        
        # Test routing user prompts dynamically
        prompt1 = "Explain the mechanics of the gradient descent algorithm"
        prompt2 = "Extract user data and output as a valid json table"
        prompt3 = "Hi, what is your favorite color?"
        
        print(f"   • Prompt: '{prompt1}'\n     → Routed to: '{sem_router.route(prompt1)}'")
        print(f"   • Prompt: '{prompt2}'\n     → Routed to: '{sem_router.route(prompt2)}'")
        print(f"   • Prompt: '{prompt3}'\n     → Routed to: '{sem_router.route(prompt3)}'")
    except Exception as e:
        print(f"   ❌ Semantic routing demo failed: {e}")

    # ---------------------------------------------------------------------------
    # 7.10. REQUEST/RESPONSE MIDDLEWARE HOOKS
    # ---------------------------------------------------------------------------
    print("\n🪝 3.10. Request/Response Middleware Hooks in Action...")
    try:
        # Register simple async middleware hooks
        async def before_hook(model: str, messages: List[dict], kwargs: dict):
            print(f"     [Middleware ON_BEFORE] Intercepting request to model '{model}' with {len(messages)} messages.")

        async def after_hook(model: str, response):
            print(f"     [Middleware ON_AFTER] Intercepting response from model '{model}'. Latency: {response.latency_ms:.0f}ms")

        client.on_before = before_hook
        client.on_after = after_hook

        print("   [Middleware Demo] Sending query...")
        await client.complete(
            model="openai/gpt-4o-mini",
            prompt="Tell me a 1-word joke."
        )

        # Reset hooks so they don't affect subsequent calls in the demo
        client.on_before = None
        client.on_after = None
    except Exception as e:
        print(f"   ❌ Middleware hooks demo failed: {e}")

    # ---------------------------------------------------------------------------
    # 7.11. PARALLEL BATCH COMPLETIONS
    # ---------------------------------------------------------------------------
    print("\n⚡ 3.11. Parallel Batch Completions in Action...")
    try:
        prompts = [
            "Explain RAG in 5 words.",
            "Explain LoRA in 5 words.",
            "Explain RLHF in 5 words."
        ]
        print(f"   [Batch Run] Executing {len(prompts)} prompts in parallel with concurrency=3...")
        batch_responses = await client.complete_batch(
            model="openai/gpt-4o-mini",
            prompts=prompts,
            concurrency=3
        )
        for i, resp in enumerate(batch_responses):
            if resp:
                print(f"     • Prompt: '{prompts[i]}' → Result: '{resp.content.strip()}'")
            else:
                print(f"     • Prompt: '{prompts[i]}' → Failed")
    except Exception as e:
        print(f"   ❌ Batch completions demo failed: {e}")

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
