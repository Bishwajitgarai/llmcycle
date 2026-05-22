<div align="center">

# LLMCycle ♻️
### The Production-Grade Universal LLM Router

**Created by [Bishwajit Garai](https://github.com/Bishwajitgarai)** — built from real pain, shipped for everyone.

[![PyPI Version](https://img.shields.io/pypi/v/llmcycle.svg)](https://pypi.org/project/llmcycle/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub Stars](https://img.shields.io/github/stars/Bishwajitgarai/llmcycle?style=social)](https://github.com/Bishwajitgarai/llmcycle)

📦 [PyPI](https://pypi.org/project/llmcycle/) &nbsp;·&nbsp; 🐙 [GitHub](https://github.com/Bishwajitgarai/llmcycle) &nbsp;·&nbsp; 📖 [Docs](#-30-second-quickstart) &nbsp;·&nbsp; 🤝 [Contribute](#-contributing)

</div>

---

**LLMCycle** is an enterprise-grade universal LLM routing framework with zero mandatory dependencies.
Route across **70+ providers**, rotate **unlimited API keys**, handle **every 4xx/5xx error gracefully**,
and stream with **zero interruptions** — even if your provider dies mid-response.

---

## 💡 The Origin Story — Why We Built This

> *"I was building a production AI product and kept hitting the same walls — rate limits at 2 AM,
> API keys burning out mid-stream, no single library that handled all of it cleanly.
> I had to build the solution I wished existed."*
> — **Bishwajit Garai**, creator of LLMCycle

### The Problems We Faced

**1. 429 Rate Limits Killed Production Traffic**
When you run at scale, `429 Too Many Requests` is not an edge case — it's a daily reality.
Existing routers would crash the entire request. We needed per-key cooldowns with auto-recovery.

**2. API Keys Burned Out Without Warning**
With multiple keys across multiple providers, a single auth failure (`401`) would silently kill
an entire provider. There was no library that tracked key health, disabled bad keys, and
automatically rotated to healthy ones.

**3. Mid-Stream Failures Were Catastrophic**
Streaming a 2000-token response and having the provider drop the connection at token 1800
meant starting from scratch. We needed seamless failover that captures partial context
and continues from another provider without the user noticing.

**4. Managing 70+ Provider Configs Was Painful**
Every provider has a different SDK, different error format, different auth header.
We needed one unified interface that auto-discovers providers from `.env` keys
— no boilerplate, no per-provider setup.

**5. There Was No Visibility**
No dashboard, no analytics, no way to see which keys were healthy, which providers
were slow, or how many tokens you were burning. We built all of that in.

**The result: LLMCycle** — one library that handles all of it, open source and free.

---

## ⚡ 30-Second Quickstart

```bash
pip install llmcycle
```

```python
import asyncio
from llmcycle import LLMCycle

async def main():
    client = LLMCycle()   # auto-loads from .env

    # Streaming with automatic failover
    async for chunk in client.stream("openai/gpt-4o-mini", "Explain RAG in 3 bullet points"):
        print(chunk, end="", flush=True)

asyncio.run(main())
```

---

## 🏆 Why LLMCycle Beats LiteLLM

| Feature | LiteLLM | **LLMCycle** |
|---|---|---|
| Multi-key per provider | ❌ | ✅ Unlimited keys, auto round-robin |
| 429 Rate-Limit handling | Basic | ✅ Per-key cooldown, auto-recovery |
| 401 Auth error | Raises exception | ✅ Disables key, auto-rotates |
| Mid-stream failover | ❌ | ✅ Captures partial text + continues |
| Sort-order routing | Basic | ✅ Priority / Round-Robin / Lowest-Latency |
| Auto provider discovery | ❌ | ✅ Reads `*_API_KEYS` from `.env` |
| 70+ providers | ✅ | ✅ Same coverage |
| Web Dashboard | ❌ | ✅ Token-auth REST API + SPA UI |
| Zero mandatory deps | ❌ | ✅ `httpx` + `pydantic` only |

---

## ⚙️ Configuration (`.env`)

```env
# ── Keys: comma-separate for multi-key load balancing ──
OPENAI_API_KEYS=sk-key1,sk-key2,sk-key3
DEEPSEEK_API_KEYS=sk-ds-1,sk-ds-2
GROQ_API_KEYS=gsk-abc
TOGETHER_API_KEYS=ta-xyz
OLLAMA_API_KEYS=local                     # Ollama needs no real key

# ── Override any base URL ──
OLLAMA_BASE_URL=http://localhost:11434/v1

# ── Dashboard auth ──
LLMCYCLE_USER_ADMIN=admin
LLMCYCLE_USER_ADMIN_PAASWORD=admin
```

---

## 💻 Full SDK Usage

### Init with fallback chains

```python
from llmcycle import LLMCycle
from llmcycle.core.router import RoutingStrategy

client = LLMCycle(
    env_path=".env",
    fallbacks={
        # provider-level: if deepseek is down, try groq, then openai
        "deepseek": ["groq", "openai"],

        # model-level: more specific, takes precedence
        "deepseek/deepseek-chat": [
            "groq/llama-3.1-70b-versatile",
            "openai/gpt-4o-mini",
        ],
    },
    strategy=RoutingStrategy.PRIORITY,   # or ROUND_ROBIN, LOWEST_LATENCY
)
```

### List providers + keys health

```python
providers = client.get_providers()
# → ['openai', 'deepseek', 'groq', 'together', 'ollama']

for p in providers:
    stats = client.key_manager.key_count(p)
    print(f"[{p}] {stats['active']}/{stats['total']} keys active")
    print(client.get_key_stats(p))
```

### Fetch models from a provider

```python
models = await client.get_models("groq")
print(models)  # ['llama-3.1-70b-versatile', 'mixtral-8x7b-32768', ...]
```

### Non-streaming completion

```python
response = await client.complete(
    model="deepseek/deepseek-chat",
    prompt="What is RAG?",
    temperature=0.7,
    max_tokens=512,
)
print(response.content)
print(f"Provider: {response.provider}, Latency: {response.latency_ms:.0f}ms")
```

### Resilient streaming

```python
# If deepseek drops mid-stream → silently continues with groq
async for chunk in client.stream("deepseek/deepseek-chat", "Write a haiku"):
    print(chunk, end="", flush=True)
```

### Manual provider registration (no `.env` needed)

```python
client.add_provider(
    name="myprovider",
    api_keys=["sk-abc", "sk-def"],
    base_url="https://api.myprovider.com/v1",
)
```

---

## 🛡️ Error Handling

LLMCycle classifies every HTTP error into a specific exception and acts accordingly:

| HTTP Status | Exception | Action Taken |
|---|---|---|
| `429` rate-limit | `RateLimitError` | Rotate key, wait cooldown, retry |
| `429` quota | `QuotaExceededError` | Rotate key, 1hr cooldown |
| `402` payment | `QuotaExceededError` | Rotate key, 1hr cooldown |
| `401` auth | `AuthenticationError` | Permanently disable key |
| `400` content | `ContentPolicyError` | **Fail fast — do NOT retry** |
| `400` bad req | `ProviderError` | Try next provider |
| `5xx` server | `ProviderError` | Try next provider |
| Stream drop | `StreamInterruptedError` | Failover with partial text context |

You can catch them individually:

```python
from llmcycle import RateLimitError, AuthenticationError, AllProvidersFailedError

try:
    resp = await client.complete("openai/gpt-4o", "Hello")
except AuthenticationError as e:
    print(f"Bad key for {e.provider}")
except AllProvidersFailedError as e:
    print(f"All providers failed: {e.errors}")
```

---

## 🖥️ Web Dashboard

```bash
uv run llmcycle ui
# → http://127.0.0.1:8000
```

Login with `LLMCYCLE_USER_ADMIN` / `LLMCYCLE_USER_ADMIN_PAASWORD` from your `.env`.  
The UI uses a **token-based REST API** (`/api/token` → Bearer token), not server-side rendering.

---

## 🌐 Supported Providers (70+)

### Frontier / Cloud
| Provider | Env Prefix | Base URL |
|---|---|---|
| OpenAI | `OPENAI` | `https://api.openai.com/v1` |
| Anthropic | `ANTHROPIC` | `https://api.anthropic.com/v1` |
| Google AI Studio | `GOOGLE` | `https://generativelanguage.googleapis.com/v1beta` |
| Azure OpenAI | `AZURE` | Custom `AZURE_BASE_URL` required |
| AWS Bedrock | `AWS_BEDROCK` | Custom region URL |

### Fast Inference / Aggregators
| Provider | Env Prefix | Base URL |
|---|---|---|
| Groq | `GROQ` | `https://api.groq.com/openai/v1` |
| Together AI | `TOGETHER` | `https://api.together.xyz/v1` |
| Fireworks AI | `FIREWORKS` | `https://api.fireworks.ai/inference/v1` |
| Perplexity | `PERPLEXITY` | `https://api.perplexity.ai` |
| OpenRouter | `OPENROUTER` | `https://openrouter.ai/api/v1` |
| DeepInfra | `DEEPINFRA` | `https://api.deepinfra.com/v1/openai` |
| Anyscale | `ANYSCALE` | `https://api.endpoints.anyscale.com/v1` |
| Novita AI | `NOVITA` | `https://api.novita.ai/v3/openai` |
| Featherless | `FEATHERLESS` | `https://api.featherless.ai/v1` |
| Lambda AI | `LAMBDA` | `https://api.lambdalabs.com/v1` |
| SambaNova | `SAMBANOVA` | `https://api.sambanova.ai/v1` |
| Cerebras | `CEREBRAS` | `https://api.cerebras.ai/v1` |
| Hyperbolic | `HYPERBOLIC` | `https://api.hyperbolic.xyz/v1` |
| Nebius AI | `NEBIUS` | `https://api.studio.nebius.ai/v1` |
| Nscale | `NSCALE` | `https://inference.api.nscale.com/v1` |

### Specialized
| Provider | Env Prefix | Base URL |
|---|---|---|
| DeepSeek | `DEEPSEEK` | `https://api.deepseek.com/v1` |
| Mistral AI | `MISTRAL` | `https://api.mistral.ai/v1` |
| Codestral | `CODESTRAL` | `https://codestral.mistral.ai/v1` |
| Cohere | `COHERE` | `https://api.cohere.com/v1` |
| AI21 | `AI21` | `https://api.ai21.com/studio/v1` |
| xAI (Grok) | `XAI` | `https://api.x.ai/v1` |
| Nvidia NIM | `NVIDIA_NIM` | `https://integrate.api.nvidia.com/v1` |
| GitHub Models | `GITHUB` | `https://models.inference.ai.azure.com` |
| Vercel AI | `VERCEL` | `https://ai-gateway.vercel.sh` |
| FriendliAI | `FRIENDLIAI` | `https://inference.friendli.ai/v1` |

### Chinese / Asia
| Provider | Env Prefix | Base URL |
|---|---|---|
| Qwen (DashScope) | `QWEN` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Moonshot AI | `MOONSHOT` | `https://api.moonshot.cn/v1` |
| MiniMax | `MINIMAX` | `https://api.minimax.chat/v1` |
| Zhipu (Z.AI) | `ZHIPU` | `https://open.bigmodel.cn/api/paas/v4` |
| Volcano Engine | `VOLCANO` | `https://ark.cn-beijing.volces.com/api/v3` |

### Enterprise / Cloud
| Provider | Env Prefix | Note |
|---|---|---|
| Databricks | `DATABRICKS` | Set `DATABRICKS_BASE_URL` |
| Snowflake | `SNOWFLAKE` | Set `SNOWFLAKE_BASE_URL` |
| WatsonX | `WATSONX` | `https://us-south.ml.cloud.ibm.com` |
| SAP AI Hub | `SAP` | Enterprise endpoint |
| Oracle OCI | `OCI` | Regional endpoint |
| Cloudflare AI | `CLOUDFLARE` | Set `CLOUDFLARE_BASE_URL` |
| Heroku | `HEROKU` | `https://llm.api.heroku.com/v1` |
| OVHCloud | `OVH` | EU sovereign cloud |
| Scaleway | `SCALEWAY` | `https://api.scaleway.ai/v1` |

### Local / Self-Hosted
| Provider | Env Prefix | Default URL |
|---|---|---|
| Ollama | `OLLAMA` | `http://localhost:11434/v1` |
| LM Studio | `LM_STUDIO` | `http://localhost:1234/v1` |
| vLLM | `VLLM` | `http://localhost:8000/v1` |
| Llamafile | `LLAMAFILE` | `http://localhost:8080/v1` |
| Xinference | `XINFERENCE` | `http://localhost:9997/v1` |

> **Any OpenAI-compatible provider works** — just set `MYPROVIDER_API_KEYS=...` and `MYPROVIDER_BASE_URL=https://...`

---

## 🔌 Routing Strategies

```python
from llmcycle.core.router import RoutingStrategy

RoutingStrategy.PRIORITY        # Default: follow your fallback sort order
RoutingStrategy.ROUND_ROBIN     # Cycle across all providers equally
RoutingStrategy.LOWEST_LATENCY  # Always pick the statistically fastest provider
```

---

## 🚀 CLI

```bash
llmcycle providers    # List all loaded providers + key health
llmcycle ui           # Start web dashboard (http://127.0.0.1:8000)
llmcycle ui --port 9000 --reload
```

---

## 🗄️ Storage Layer

Persist sessions, users, requests, and full conversation history to **any one** backend.
Pick exactly one — configured via `.env` or passed directly to the class.

### Install your backend

```bash
uv add llmcycle[sqlite]    # SQLite  — zero config, local dev
uv add llmcycle[postgres]  # PostgreSQL
uv add llmcycle[mysql]     # MySQL / MariaDB
uv add llmcycle[mssql]     # Microsoft SQL Server
uv add llmcycle[mongo]     # MongoDB
uv add llmcycle[redis]     # Redis (best for sessions + caching)
uv add llmcycle[storage]   # All backends at once
```

### Configure via `.env` (recommended)

```env
# Choose ONE backend
LLMCYCLE_STORAGE_BACKEND=postgres
LLMCYCLE_STORAGE_URL=postgresql+asyncpg://user:pass@localhost/mydb

# Optional — default schema and table/collection prefix
LLMCYCLE_STORAGE_SCHEMA=analytics       # PostgreSQL/MSSQL schema
LLMCYCLE_STORAGE_TABLE_PREFIX=llm_      # Default: "llmc_"
```

### Or pass directly (overrides env)

```python
from llmcycle.storage import StorageBackend, StorageManager

# SQLite — zero config
store = StorageManager(StorageBackend.SQLITE)

# PostgreSQL with custom schema + prefix
store = StorageManager(
    backend=StorageBackend.POSTGRES,
    url="postgresql+asyncpg://user:pass@host/db",
    schema="analytics",      # tables live in "analytics" schema
    table_prefix="llm_",     # → analytics.llm_requests, analytics.llm_users ...
)

# MongoDB — schema = database name, prefix = collection prefix
store = StorageManager(
    backend=StorageBackend.MONGO,
    url="mongodb://localhost:27017",
    schema="my_llm_db",
    table_prefix="prod_",    # → prod_requests, prod_sessions ...
)

# Redis — prefix applies to all keys
store = StorageManager(
    backend=StorageBackend.REDIS,
    url="redis://localhost:6379/0",
    table_prefix="myapp:",
)

await store.connect()
```

### Priority: direct args > env vars > defaults

| Env Var | Default | Description |
|---|---|---|
| `LLMCYCLE_STORAGE_BACKEND` | — | `sqlite` / `postgres` / `mysql` / `mssql` / `mongo` / `redis` |
| `LLMCYCLE_STORAGE_URL` | per-backend default | Connection string |
| `LLMCYCLE_STORAGE_SCHEMA` | `None` | DB schema (Postgres/MSSQL) or DB name (MongoDB) |
| `LLMCYCLE_STORAGE_TABLE_PREFIX` | `llmc_` | Prefix for all tables / collections / keys |

### Ping — test connectivity

```python
result = await store.ping()
# {"ok": True, "backend": "postgres", "latency_ms": 1.4}
# {"ok": False, "backend": "redis",   "error": "Connection refused"}
```

### CRUD — Users, Teams, Sessions, Requests, History

```python
from llmcycle.storage.models import User, Session, LLMRequest, HistoryMessage

# Users
user = await store.create_user(User(username="alice", email="alice@acme.com", role="admin"))
user = await store.get_user(user.id)
user = await store.get_user_by_username("alice")
users = await store.list_users(team_id="team-123")
await store.update_user(user)
await store.delete_user(user.id)

# Sessions
session = await store.create_session(Session(user_id=user.id, model="gpt-4o"))
session.total_requests += 1
await store.update_session(session)
sessions = await store.list_sessions(user_id=user.id, limit=20)

# Requests (auto-logged per LLM call)
req = await store.save_request(LLMRequest(
    model="gpt-4o-mini", provider="openai",
    prompt="What is RAG?",  response="RAG is...",
    prompt_tokens=12, completion_tokens=80,
    latency_ms=340, status="success",
    session_id=session.id, user_id=user.id,
))
requests = await store.list_requests(session_id=session.id)

# History (conversation turns)
await store.append_history(HistoryMessage(session_id=session.id, role="user",      content="Hello"))
await store.append_history(HistoryMessage(session_id=session.id, role="assistant", content="Hi!"))
history = await store.get_history(session.id, limit=100)
await store.clear_history(session.id)
```

### Analytics

```python
import time

yesterday = time.time() - 86400

# Overall summary
stats = await store.analytics.summary(from_ts=yesterday)
# {
#   "total_requests": 1200,
#   "total_tokens": 540000,
#   "avg_latency_ms": 312.4,
#   "p95_latency_ms": 890.2,
#   "error_rate": 0.02,
#   "fallback_rate": 0.05,
# }

# Filter by user / session / provider / model / time range
user_stats = await store.analytics.summary(user_id="u-abc", from_ts=yesterday)

# Breakdown per provider
by_prov = await store.analytics.by_provider(from_ts=yesterday)
# [{"provider": "openai", "requests": 800, "tokens": 380000, "avg_latency_ms": 340, "errors": 4}, ...]

# Breakdown per model
by_model = await store.analytics.by_model()

# Breakdown per user (sorted by token usage)
by_user = await store.analytics.by_user(from_ts=yesterday)

# Breakdown per session
by_session = await store.analytics.by_session(user_id="u-abc")

# Time-series (bucket = "minute" | "hour" | "day")
timeseries = await store.analytics.timeseries(bucket="hour", from_ts=yesterday)
# [{"bucket": "2025-05-22T14:00", "requests": 45, "tokens": 18000, "errors": 1, "avg_latency_ms": 290}, ...]

# Top errors
errors = await store.analytics.top_errors(limit=10)
# [{"error": "Rate limited", "count": 12, "provider": "openai"}, ...]
```

### Purge / Delete by date range

```python
import time

# Delete request logs older than 30 days
thirty_days_ago = time.time() - 30 * 86400
result = await store.purge_by_range(to_ts=thirty_days_ago)
# {"deleted": {"requests": 4820}}

# Delete everything in a specific time window
result = await store.purge_by_range(
    from_ts=1700000000,
    to_ts=1700086400,
    entities=["requests", "history", "sessions"],  # or ["all"]
)
# {"deleted": {"requests": 120, "history": 340, "sessions": 15}}

# Wipe all cached request logs (no time range = all)
result = await store.purge_by_range(entities=["requests"])
```

### Async context manager

```python
async with StorageManager(StorageBackend.SQLITE) as store:
    await store.create_user(User(username="bob"))
    stats = await store.analytics.summary()
    result = await store.ping()
# auto-disconnects on exit
```

---

## 🧪 Running Tests

```bash
# All tests (34 core + 40+ storage)
uv run pytest tests/ -v

# Only storage tests (uses in-memory SQLite — no external DB needed)
uv run pytest tests/test_storage.py -v

# Only core LLM routing tests
uv run pytest tests/test_llmcycle.py -v
```

---

## 🤝 Contributing

LLMCycle was born from real-world pain. Every feature exists because someone hit a wall in production.
**We welcome contributions of all kinds** — new provider integrations, bug fixes, storage backends,
dashboard improvements, or just better documentation.

### How to contribute

```bash
# 1. Fork & clone
git clone https://github.com/Bishwajitgarai/llmcycle.git
cd llmcycle

# 2. Install in dev mode with all extras
uv sync --group dev
uv add sqlalchemy aiosqlite --dev

# 3. Make your changes
# 4. Run tests — all must pass
uv run pytest tests/ -v

# 5. Open a Pull Request
```

### What we'd love help with

| Area | Ideas |
|---|---|
| **New providers** | Add any OpenAI-compatible API to `providers/registry.py` |
| **Storage backends** | DynamoDB, Cassandra, ClickHouse |
| **Analytics** | Cost estimation, token pricing per model |
| **Dashboard** | Charts, export, multi-user auth |
| **Testing** | Integration tests for each provider |
| **Docs** | Tutorials, deployment guides, video walkthroughs |

### Contribution guidelines

- Keep PRs focused — one feature or fix per PR
- Add tests for any new functionality
- Follow existing code style (no external formatters required)
- Update `README.md` if you add a new provider or feature
- Be kind — this is a welcoming community

### Found a bug? Have an idea?

Open an issue at [github.com/Bishwajitgarai/llmcycle/issues](https://github.com/Bishwajitgarai/llmcycle/issues).
No template required — just describe what you saw and what you expected.

---

## 👤 Author

<div align="center">

**Built with ❤️ by [Bishwajit Garai](https://github.com/Bishwajitgarai)**

*"Stop fighting your LLM infrastructure. Let LLMCycle handle it."*

[![GitHub Follow](https://img.shields.io/github/followers/Bishwajitgarai?style=social)](https://github.com/Bishwajitgarai)
[![PyPI](https://img.shields.io/pypi/dm/llmcycle?label=PyPI%20downloads)](https://pypi.org/project/llmcycle/)

</div>

---

<div align="center">

⭐ **If LLMCycle saved you hours, please star the repo — it helps others find it.**

[⭐ Star on GitHub](https://github.com/Bishwajitgarai/llmcycle) &nbsp;·&nbsp; [📦 PyPI](https://pypi.org/project/llmcycle/) &nbsp;·&nbsp; [🐛 Report Bug](https://github.com/Bishwajitgarai/llmcycle/issues) &nbsp;·&nbsp; [💡 Request Feature](https://github.com/Bishwajitgarai/llmcycle/issues)

</div>
