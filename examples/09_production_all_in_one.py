"""
LLMCycle — Production All-in-One
==================================
The canonical "boot once, use everywhere" production pattern.

Architecture:
  - API keys loaded from REDIS (centralized, hot-reloadable, no redeploy needed)
  - All requests auto-logged to POSTGRESQL (tokens, latency, cost, errors)
  - Guardrails, injection guard, budget, auto-trim — all on by default
  - Fallbacks + groups declared at startup — app code stays clean

Redis key format (set these in Redis before running):
    SET OPENAI_API_KEYS    "sk-key1,sk-key2"
    SET ANTHROPIC_API_KEYS "sk-ant-..."
    SET GROQ_API_KEYS      "gsk_..."

PostgreSQL:
    postgresql+asyncpg://user:password@localhost:5432/llmcycle_db

File structure (simulated in one file for clarity):
    app/
      llm.py          ← declare once
      summarizer.py   ← import llm, just call it
      extractor.py    ← import llm, just call it
      agent.py        ← import llm, use Tool class
      main.py         ← boot once, call all services
"""
import asyncio
import sys
from typing import List
from pydantic import BaseModel, Field

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from llmcycle import LLMCycle, Tool, ToolParameter
from llmcycle.client import ConfigSource
from llmcycle.schema import RoutingStrategy
from llmcycle.storage import StorageManager, StorageBackend

# =============================================================================
# ── llm.py — Configure once. Import `llm` everywhere.
# =============================================================================

store = StorageManager(
    backend=StorageBackend.POSTGRES,
    url="postgresql+asyncpg://user:password@localhost:5432/llmcycle_db"
)

llm = LLMCycle(
    # Load API keys from Redis — no .env file, fully centralized
    config_source=ConfigSource.REDIS,
    redis_url="redis://localhost:6379/0",

    # Routing
    strategy=RoutingStrategy.PRIORITY,

    # Safety — active on every single request automatically
    auto_trim_context=True,     # Silently trims if messages exceed context limit
    guardrail=True,             # Masks PII (emails, phone, keys) before sending to LLM
    injection_guard=True,       # Blocks prompt injection / jailbreak attempts

    # Budget — raises BudgetExceededError if session cost exceeds this
    max_cost_usd=50.00,

    # Observability — every request auto-logged to PostgreSQL
    storage=store,
    session_id="prod-session",
    team_id="backend-team",
)

async def boot():
    """Call ONCE when your application starts."""
    await store.connect()

    # Fallbacks: primary fails → try backups automatically
    await llm.router.fallbacks.add(
        primary_model="anthropic/claude-3-5-sonnet",
        fallback_models=["openai/gpt-4o", "gemini/gemini-1.5-pro"]
    )
    # fast group: cheap, quick tasks
    await llm.router.groups.add(
        group_id="fast",
        models=["groq/llama-3.1-8b-instant", "openai/gpt-4o-mini"]
    )
    # smart group: complex reasoning tasks
    await llm.router.groups.add(
        group_id="smart",
        models=["anthropic/claude-3-5-sonnet", "openai/gpt-4o"]
    )


# =============================================================================
# ── summarizer.py — Simple task, uses the fast group
# =============================================================================

async def summarize(text: str) -> str:
    response = await llm.complete(
        group="fast",
        prompt=f"Summarize in one sentence:\n\n{text}"
    )
    return response.content.strip()


# =============================================================================
# ── extractor.py — Structured output, returns a Pydantic object
# =============================================================================

class JobPosting(BaseModel):
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    skills: List[str] = Field(description="Required technical skills")
    experience_years: int = Field(description="Minimum years of experience")
    remote: bool = Field(description="Is the role remote?")

async def extract_job(raw_text: str) -> JobPosting:
    """complete_structured returns a validated Pydantic object directly."""
    return await llm.complete_structured(
        model="openai/gpt-4o-mini",
        prompt=f"Extract job posting details from:\n\n{raw_text}",
        schema=JobPosting,
    )


# =============================================================================
# ── agent.py — Agentic tool calling using the Tool class (no raw dicts!)
# =============================================================================

# Define tools using the clean Tool class — no raw OpenAI dicts needed
weather_tool = Tool(
    name="get_weather",
    description="Get the current weather for a city.",
    parameters={
        "city": ToolParameter(type="string", description="City name, e.g. London"),
        "unit": ToolParameter(
            type="string",
            description="Temperature unit",
            enum=["celsius", "fahrenheit"]
        ),
    },
    required=["city"],
)

search_tool = Tool(
    name="search_docs",
    description="Search internal documentation for a given query.",
    parameters={
        "query": ToolParameter(type="string", description="Search query string"),
    },
)

async def tool_executor(name: str, args: dict):
    """LLMCycle calls this when the LLM wants to use a tool."""
    if name == "get_weather":
        city = args.get("city", "Unknown")
        weather_db = {
            "London": {"temp": 12, "condition": "Rainy", "unit": "celsius"},
            "Tokyo": {"temp": 24, "condition": "Sunny", "unit": "celsius"},
        }
        return weather_db.get(city, {"temp": 20, "condition": "Unknown"})

    if name == "search_docs":
        return {"results": [f"Doc about: {args.get('query', '')}", "Related guide", "API reference"]}

    return {"error": f"Unknown tool: {name}"}

async def run_agent(prompt: str) -> str:
    """Run a full agentic loop — LLM calls tools, LLMCycle handles everything."""
    response = await llm.complete_with_tools(
        model="openai/gpt-4o-mini",
        prompt=prompt,
        tools=[weather_tool, search_tool],   # ← Tool objects, not raw dicts
        tool_executor=tool_executor,
        max_tool_calls=5,
    )
    return response.content.strip()


# =============================================================================
# ── batch_processor.py — Concurrent batch completions
# =============================================================================

async def batch_define(terms: List[str]) -> List[str]:
    responses = await llm.complete_batch(
        model="openai/gpt-4o-mini",
        prompts=[f"Define '{t}' in 8 words." for t in terms],
        concurrency=5,
    )
    return [r.content.strip() if r else "Failed" for r in responses]


# =============================================================================
# ── main.py — Boot once. Use everywhere.
# =============================================================================

async def main():
    print("=" * 60)
    print("  LLMCycle Production App — Redis Config + PostgreSQL DB")
    print("=" * 60)

    await boot()
    print("✅ Booted: Redis config loaded, PostgreSQL connected.\n")

    # 1. Summarization
    print("── 1. Summarization (fast group) ─────────────────────────")
    summary = await summarize(
        "LLMCycle is an enterprise LLM router with zero mandatory dependencies. "
        "It routes across 70+ providers, rotates unlimited API keys, and handles "
        "every 4xx/5xx error gracefully with mid-stream failover."
    )
    print(f"  {summary}\n")

    # 2. Structured Extraction
    print("── 2. Structured Extraction (Pydantic) ────────────────────")
    job = await extract_job(
        "Senior Backend Engineer at Acme Corp. Requires 5+ years Python, "
        "FastAPI, PostgreSQL, Kubernetes. The role is fully remote."
    )
    print(f"  Title     : {job.title}")
    print(f"  Company   : {job.company}")
    print(f"  Skills    : {', '.join(job.skills)}")
    print(f"  Experience: {job.experience_years}+ years")
    print(f"  Remote    : {job.remote}\n")

    # 3. Streaming
    print("── 3. Streaming (smart group) ─────────────────────────────")
    print("  Streaming: ", end="", flush=True)
    async for chunk in llm.stream(
        group="smart",
        prompt="In two sentences, explain why LLM fallbacks matter in production."
    ):
        print(chunk, end="", flush=True)
    print("\n")

    # 4. Agentic Tool Calling (using Tool class)
    print("── 4. Tool Calling (Tool class) ────────────────────────────")
    agent_response = await run_agent(
        "What's the weather in London? Also search for 'LLM routing best practices'."
    )
    print(f"  Agent: {agent_response}\n")

    # 5. Batch Processing
    print("── 5. Batch Processing (5 concurrent) ──────────────────────")
    terms = ["RAG", "LoRA", "RLHF", "KV Cache", "Chain-of-Thought"]
    definitions = await batch_define(terms)
    for term, defn in zip(terms, definitions):
        print(f"  {term:20s}: {defn}")

    # 6. Analytics from PostgreSQL
    print("\n── 6. PostgreSQL Analytics ─────────────────────────────────")
    summary_stats = await store.analytics.summary()
    print(f"  Total Requests : {summary_stats.get('total_requests', 0)}")
    print(f"  Total Tokens   : {summary_stats.get('total_tokens', 0)}")
    print(f"  Avg Latency    : {summary_stats.get('avg_latency_ms', 0):.1f}ms")
    print(f"  Error Rate     : {summary_stats.get('error_rate', 0) * 100:.1f}%")

    # 7. Cost summary
    print("\n── 7. Session Cost ─────────────────────────────────────────")
    cost = llm.get_cost_summary()
    print(f"  Spent  : ${cost['total_cost_usd']:.6f}")
    print(f"  Budget : ${cost['budget_usd']:.2f}")

    await store.disconnect()
    print("\n✅ Done. Run `llmcycle ui` to see live analytics dashboard.")

if __name__ == "__main__":
    asyncio.run(main())
