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
# pip
pip install llmcycle

# uv (recommended — faster)
uv add llmcycle
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

## 🏆 How LLMCycle Compares

> We respect every library below — they solve different problems. This table focuses on **LLM routing & reliability** features specifically.

| Feature | LLMCycle | LiteLLM | LangChain | OpenAI SDK | Portkey | aisuite |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Multi-key per provider** | ✅ Unlimited | ❌ | ❌ | ❌ | ✅ Paid | ❌ |
| **Auto key round-robin** | ✅ | ❌ | ❌ | ❌ | ✅ Paid | ❌ |
| **429 per-key cooldown + recovery** | ✅ | Basic | ❌ | ❌ | ✅ Paid | ❌ |
| **401 → auto disable key** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Mid-stream failover** | ✅ with context | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Provider auto-discovery from `.env`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Priority / Round-Robin / Latency routing** | ✅ | ❌ | ❌ | ❌ | ✅ Paid | ❌ |
| **Canary & Weighted Splits** | ✅ Built-in (RoutingStrategy.CANARY) | ❌ | ❌ | ❌ | ✅ Paid | ❌ |
| **Intent-Based Semantic Routing** | ✅ Built-in (SemanticRouter) | ❌ | ✅ Basic (Hub config) | ❌ | ❌ | ❌ |
| **Fallback chains (model + provider level)** | ✅ | Partial | Partial | ❌ | ✅ Paid | ❌ |
| **Pluggable Prompt Caching** | ✅ Built-in (Memory/SQL/Redis) | ✅ Basic (Redis, heavy) | ✅ Basic | ❌ | ✅ Paid | ❌ |
| **Client-Side Rate Limiting** | ✅ Built-in (RPM/TPM bucket) | ✅ Basic | ❌ | ❌ | ✅ Paid | ❌ |
| **PII & Secrets Guardrails** | ✅ Built-in (Mask/Unmask) | ✅ Basic | ✅ Basic | ❌ | ✅ Paid | ❌ |
| **Budget Enforcement** | ✅ Built-in (Cost cap) | ✅ Basic | ❌ | ❌ | ✅ Paid | ❌ |
| **Context Window Auto-Trim** | ✅ Built-in | ❌ | ✅ Basic | ❌ | ❌ | ❌ |
| **Structured Pydantic Output** | ✅ Tool-calling (default) + JSON-prompt fallback | ✅ Basic | ✅ Basic | ✅ Basic | ❌ | ❌ |
| **Agentic Tool Loops (with guard)** | ✅ Built-in loop (complete_with_tools) | ❌ | ✅ Basic | ❌ | ❌ | ❌ |
| **Multimodal Attachments (local/S3)** | ✅ Local/S3 storage | Basic (payload only) | Basic (payload only) | Basic (payload only) | Partial | ❌ |
| **Live Model Discovery** | ✅ Parallel CLI/SDK | ✅ SDK | ❌ | Basic | ❌ | ❌ |
| **70+ providers** | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| **Streaming** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Parallel Batch Completions** | ✅ Built-in (complete_batch) | ✅ Basic | ✅ Basic | ❌ | ❌ | ❌ |
| **Request/Response Middleware** | ✅ Hooks (on_before/on_after) | ✅ Basic | ✅ Basic | ❌ | ❌ | ❌ |
| **Storage layer (SQL/Mongo/Redis)** | ✅ Built-in | ❌ | Partial | ❌ | ❌ | ❌ |
| **Session / user / history tracking** | ✅ | ❌ | Partial | ❌ | ✅ Paid | ❌ |
| **Analytics (tokens, latency, errors)** | ✅ | ❌ | ❌ | ❌ | ✅ Paid | ❌ |
| **Purge data by date range** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Web dashboard (SPA + REST API)** | ✅ | ❌ | ❌ | ❌ | ✅ Paid | ❌ |
| **Zero mandatory extra deps** | ✅ httpx+pydantic | ❌ Heavy | ❌ Heavy | ✅ | ❌ | ✅ |
| **Fully open source & free** | ✅ MIT | ✅ MIT | ✅ MIT | ✅ | ❌ Freemium | ✅ MIT |
| **Self-hostable** | ✅ | ✅ | ✅ | ✅ | ❌ Cloud | ✅ |

> **Legend:** ✅ = Supported, ❌ = Not supported, Partial = Limited support, Paid = Requires paid plan

---

## ⚙️ Automatic Environment Discovery (`.env`)

LLMCycle is designed for **zero-boilerplate configuration**. The moment you call `LLMCycle()`, it automatically scans your environment (or `.env` file) to discover, initialize, and register all LLM providers, their API keys, and endpoints.

Here is how the auto-discovery mechanism works under the hood:

### 1. The `*_API_KEYS` Pattern
LLMCycle searches for any environment variable matching the pattern `{PROVIDER}_API_KEYS`. 
* **Single Key:** `OPENAI_API_KEYS=sk-proj-...`
* **Multi-Key Load Balancing (Comma-Separated):** If you provide a comma-separated list of keys, LLMCycle automatically parses them and performs **healthy round-robin key rotation**.
  ```env
  # Comma-separate for multi-key rotation and automatic 429/401 resilience
  OPENAI_API_KEYS=sk-key1,sk-key2,sk-key3
  DEEPSEEK_API_KEYS=sk-ds-1,sk-ds-2
  ```

### 2. Provider Default Base URLs & Overrides
Every recognized provider (Groq, Anthropic, DeepSeek, Google, OpenAI, etc.) has its official production API URL registered out-of-the-box.
* **Custom Endpoints / Gateways:** You can override any provider's API endpoint dynamically by specifying `{PROVIDER}_BASE_URL`.
* **Local Models (Ollama, vLLM, LM Studio):** Since local models run locally, you can map their host addresses directly.
  ```env
  OLLAMA_API_KEYS=local                     # Local providers require no active keys
  OLLAMA_BASE_URL=http://localhost:11434/v1 # Overrides default Ollama base URL
  ```

### 3. Dynamic Custom Providers
Need to connect to a new or custom OpenAI-compatible gateway? Just set the env variables! LLMCycle will automatically register any custom provider:
```env
# Register a custom API gateway named 'mygateway'
MYGATEWAY_API_KEYS=sk-custom-123
MYGATEWAY_BASE_URL=https://api.mycustomgateway.com/v1
```
You can now immediately route queries to it: `await client.complete("mygateway/some-model", "Hello!")`!

---

### Full `.env` Example

Here is a production-ready `.env` file demonstrating all core features:

```env
# ── Frontier Providers ──
OPENAI_API_KEYS=sk-proj-key1,sk-proj-key2
ANTHROPIC_API_KEYS=sk-ant-key1
GOOGLE_API_KEYS=AIzaSy...

# ── Specialized & Fast Aggregators ──
DEEPSEEK_API_KEYS=sk-ds-1,sk-ds-2
GROQ_API_KEYS=gsk_...
TOGETHER_API_KEYS=tg-...

# ── Local & Self-Hosted Overrides ──
OLLAMA_API_KEYS=local
OLLAMA_BASE_URL=http://localhost:11434/v1

# ── Custom OpenAI-Compatible Gateways ──
MYGATEWAY_API_KEYS=sk-mykey
MYGATEWAY_BASE_URL=https://api.mygateway.com/v1

# ── Dashboard Authentication ──
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

### Fetch all live models in parallel

```python
# Fetches all dynamic live models across all active providers in parallel
all_models = await client.get_all_live_models()
# → {"openai": ["gpt-4o", ...], "groq": ["llama-3.1-70b", ...]}
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

### Auto-save every request to storage

Pass `storage=` into `LLMCycle` and every `complete()` / `stream()` call **automatically** saves an `LLMRequest` record — no manual `save_request` needed.

```python
from llmcycle import LLMCycle
from llmcycle.storage import StorageBackend, StorageManager

# Set up storage once
store = StorageManager(
    backend=StorageBackend.SQLITE,   # or POSTGRES, MONGO, REDIS ...
    table_prefix="myapp_",
)
await store.connect()

# Pass into client — all calls auto-save
client = LLMCycle(
    storage=store,
    session_id="sess-abc",   # stamped on every request (optional)
    user_id="user-123",      # stamped on every request (optional)
)

# ✅ This now auto-saves an LLMRequest record to storage
response = await client.complete("openai/gpt-4o-mini", "What is RAG?")

# ✅ Streaming also auto-saves (once stream completes)
async for chunk in client.stream("groq/llama-3.1-70b", "Write a haiku"):
    print(chunk, end="", flush=True)

# Override session/user per-call
response = await client.complete(
    model="deepseek/deepseek-chat",
    prompt="Explain transformers",
    session_id="sess-xyz",   # overrides client-level session_id
    user_id="user-456",
)

# Query what was saved
requests = await store.list_requests(user_id="user-123")
stats = await store.analytics.summary()
```

You can still manually save if needed:

```python
from llmcycle.storage.models import LLMRequest

await store.save_request(LLMRequest(
    model="gpt-4o-mini",
    provider="openai",
    prompt="What is RAG?",
    response="RAG is...",
    prompt_tokens=12,
    completion_tokens=80,
    latency_ms=340,
    status="success",
    session_id=session.id,
    user_id=user.id,
))
```

### 💡 Complete Production Example (End-to-End)

For a fully self-contained production workflow featuring database storage, multi-provider fallbacks, prompt caching, token budget limits, structured Pydantic output, and performance analytics, you can run the complete example script included in the codebase:

```bash
# Run the complete end-to-end production example
uv run examples/complete_llm_example.py
```

Here is the complete production workflow code:

```python
import asyncio
from typing import List
from pydantic import BaseModel, Field
from llmcycle import LLMCycle, RoutingStrategy
from llmcycle.storage import StorageBackend, StorageManager
from llmcycle.storage.models import User, Session

# 1. Define structured outputs
class UserProfile(BaseModel):
    name: str = Field(description="The person's name")
    skills: List[str] = Field(description="Core technical skills")
    experience_years: int = Field(description="Years of experience")

async def main():
    # 2. Setup SQLite database storage
    store = StorageManager(backend=StorageBackend.SQLITE, table_prefix="prod_")
    await store.connect()
    
    # 3. Create tracking session
    user = await store.create_user(User(username="alice", email="alice@example.com"))
    session = await store.create_session(Session(user_id=user.id, model="openai/gpt-4o-mini"))
    
    # 4. Initialize LLMCycle with Storage & Resilient Routing
    client = LLMCycle(
        env_path=".env",
        storage=store,
        session_id=session.id,
        user_id=user.id,
        strategy=RoutingStrategy.PRIORITY,
        fallbacks={
            "deepseek": ["groq", "openai"],
            "deepseek/deepseek-chat": ["groq/llama-3.1-70b-versatile", "openai/gpt-4o-mini"]
        }
    )
    
    # 5. Non-streaming request (Auto-logs metadata, latency, cost to DB)
    response = await client.complete(
        model="openai/gpt-4o-mini",
        prompt="Explain key rotation in one sentence."
    )
    print(f"[{response.provider}]: {response.content.strip()}")
    
    # 6. Resilient streaming completion with mid-stream failover fallback
    async for chunk in client.stream(
        model="openai/gpt-4o-mini",
        prompt="Write a short poem about coding."
    ):
        print(chunk, end="", flush=True)
    print()
    
    # 7. Structured Pydantic extraction
    profile: UserProfile = await client.structured_complete(
        model="openai/gpt-4o-mini",
        prompt="Alice is a backend engineer with 5 years experience skilled in Python and FastAPI.",
        response_model=UserProfile
    )
    print(f"Profile: {profile.name}, Skills: {profile.skills}")
    
    # 8. Pull production analytics in real-time from the database
    summary = await store.analytics.summary()
    print(f"Total Requests Logged: {summary.get('total_requests')}")
    print(f"Average Latency: {summary.get('avg_latency_ms'):.1f}ms")
    
    await store.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
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
| Provider | Env Prefix | API Key Pattern Example (Comma-separate for multi-key rotation) | Base URL |
|---|---|---|---|
| OpenAI | `OPENAI` | `OPENAI_API_KEYS=sk-proj-...,sk-proj-...` | `https://api.openai.com/v1` |
| Anthropic | `ANTHROPIC` | `ANTHROPIC_API_KEYS=sk-ant-...,sk-ant-...` | `https://api.anthropic.com/v1` |
| Google AI Studio | `GOOGLE` | `GOOGLE_API_KEYS=AIzaSy...,AIzaSy...` | `https://generativelanguage.googleapis.com/v1beta` |
| Azure OpenAI | `AZURE` | `AZURE_API_KEYS=key1,key2` | Custom `AZURE_BASE_URL` required |
| AWS Bedrock | `AWS_BEDROCK` | `AWS_BEDROCK_API_KEYS=key1` | Custom region URL |

### Fast Inference / Aggregators
| Provider | Env Prefix | API Key Pattern Example | Base URL |
|---|---|---|---|
| Groq | `GROQ` | `GROQ_API_KEYS=gsk_...,gsk_...` | `https://api.groq.com/openai/v1` |
| Together AI | `TOGETHER` | `TOGETHER_API_KEYS=tg-...,tg-...` | `https://api.together.xyz/v1` |
| Fireworks AI | `FIREWORKS` | `FIREWORKS_API_KEYS=fw-...,fw-...` | `https://api.fireworks.ai/inference/v1` |
| Perplexity | `PERPLEXITY` | `PERPLEXITY_API_KEYS=pplx-...,pplx-...` | `https://api.perplexity.ai` |
| OpenRouter | `OPENROUTER` | `OPENROUTER_API_KEYS=sk-or-...,sk-or-...` | `https://openrouter.ai/api/v1` |
| DeepInfra | `DEEPINFRA` | `DEEPINFRA_API_KEYS=di-...,di-...` | `https://api.deepinfra.com/v1/openai` |
| Anyscale | `ANYSCALE` | `ANYSCALE_API_KEYS=as-...,as-...` | `https://api.endpoints.anyscale.com/v1` |
| Novita AI | `NOVITA` | `NOVITA_API_KEYS=nv-...,nv-...` | `https://api.novita.ai/v3/openai` |
| Featherless | `FEATHERLESS` | `FEATHERLESS_API_KEYS=fl-...,fl-...` | `https://api.featherless.ai/v1` |
| Lambda AI | `LAMBDA` | `LAMBDA_API_KEYS=la-...,la-...` | `https://api.lambdalabs.com/v1` |
| SambaNova | `SAMBANOVA` | `SAMBANOVA_API_KEYS=sn-...,sn-...` | `https://api.sambanova.ai/v1` |
| Cerebras | `CEREBRAS` | `CEREBRAS_API_KEYS=csk-...,csk-...` | `https://api.cerebras.ai/v1` |
| Hyperbolic | `HYPERBOLIC` | `HYPERBOLIC_API_KEYS=hb-...,hb-...` | `https://api.hyperbolic.xyz/v1` |
| Nebius AI | `NEBIUS` | `NEBIUS_API_KEYS=nb-...,nb-...` | `https://api.studio.nebius.ai/v1` |
| Nscale | `NSCALE` | `NSCALE_API_KEYS=ns-...,ns-...` | `https://inference.api.nscale.com/v1` |

### Specialized
| Provider | Env Prefix | API Key Pattern Example | Base URL |
|---|---|---|---|
| DeepSeek | `DEEPSEEK` | `DEEPSEEK_API_KEYS=sk-...,sk-...` | `https://api.deepseek.com/v1` |
| Mistral AI | `MISTRAL` | `MISTRAL_API_KEYS=ms-...,ms-...` | `https://api.mistral.ai/v1` |
| Codestral | `CODESTRAL` | `CODESTRAL_API_KEYS=cs-...,cs-...` | `https://codestral.mistral.ai/v1` |
| Cohere | `COHERE` | `COHERE_API_KEYS=ch-...,ch-...` | `https://api.cohere.com/v1` |
| AI21 | `AI21` | `AI21_API_KEYS=ai21-...,ai21-...` | `https://api.ai21.com/studio/v1` |
| xAI (Grok) | `XAI` | `XAI_API_KEYS=xai-...,xai-...` | `https://api.x.ai/v1` |
| Nvidia NIM | `NVIDIA_NIM` | `NVIDIA_NIM_API_KEYS=nvapi-...,nvapi-...` | `https://integrate.api.nvidia.com/v1` |
| GitHub Models | `GITHUB` | `GITHUB_API_KEYS=ghu-...,ghu-...` | `https://models.inference.ai.azure.com` |
| Vercel AI | `VERCEL` | `VERCEL_API_KEYS=vc-...,vc-...` | `https://ai-gateway.vercel.sh` |
| FriendliAI | `FRIENDLIAI` | `FRIENDLIAI_API_KEYS=fr-...,fr-...` | `https://inference.friendli.ai/v1` |

### Chinese / Asia
| Provider | Env Prefix | API Key Pattern Example | Base URL |
|---|---|---|---|
| Qwen (DashScope) | `QWEN` | `QWEN_API_KEYS=qw-...,qw-...` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Moonshot AI | `MOONSHOT` | `MOONSHOT_API_KEYS=ms-...,ms-...` | `https://api.moonshot.cn/v1` |
| MiniMax | `MINIMAX` | `MINIMAX_API_KEYS=mm-...,mm-...` | `https://api.minimax.chat/v1` |
| Zhipu (Z.AI) | `ZHIPU` | `ZHIPU_API_KEYS=zp-...,zp-...` | `https://open.bigmodel.cn/api/paas/v4` |
| Volcano Engine | `VOLCANO` | `VOLCANO_API_KEYS=ve-...,ve-...` | `https://ark.cn-beijing.volces.com/api/v3` |

### Enterprise / Cloud
| Provider | Env Prefix | API Key Pattern Example | Note |
|---|---|---|---|
| Databricks | `DATABRICKS` | `DATABRICKS_API_KEYS=db-...,db-...` | Set `DATABRICKS_BASE_URL` |
| Snowflake | `SNOWFLAKE` | `SNOWFLAKE_API_KEYS=sf-...,sf-...` | Set `SNOWFLAKE_BASE_URL` |
| WatsonX | `WATSONX` | `WATSONX_API_KEYS=wx-...,wx-...` | `https://us-south.ml.cloud.ibm.com` |
| SAP AI Hub | `SAP` | `SAP_API_KEYS=sap-...,sap-...` | Enterprise endpoint |
| Oracle OCI | `OCI` | `OCI_API_KEYS=oci-...,oci-...` | Regional endpoint |
| Cloudflare AI | `CLOUDFLARE` | `CLOUDFLARE_API_KEYS=cf-...,cf-...` | Set `CLOUDFLARE_BASE_URL` |
| Heroku | `HEROKU` | `HEROKU_API_KEYS=hk-...,hk-...` | `https://llm.api.heroku.com/v1` |
| OVHCloud | `OVH` | `OVH_API_KEYS=ovh-...,ovh-...` | EU sovereign cloud |
| Scaleway | `SCALEWAY` | `SCALEWAY_API_KEYS=sw-...,sw-...` | `https://api.scaleway.ai/v1` |

### Local / Self-Hosted
| Provider | Env Prefix | API Key Pattern Example | Default URL |
|---|---|---|---|
| Ollama | `OLLAMA` | `OLLAMA_API_KEYS=local` | `http://localhost:11434/v1` |
| LM Studio | `LM_STUDIO` | `LM_STUDIO_API_KEYS=local` | `http://localhost:1234/v1` |
| vLLM | `VLLM` | `VLLM_API_KEYS=local` | `http://localhost:8000/v1` |
| Llamafile | `LLAMAFILE` | `LLAMAFILE_API_KEYS=local` | `http://localhost:8080/v1` |
| Xinference | `XINFERENCE` | `XINFERENCE_API_KEYS=local` | `http://localhost:9997/v1` |

> **Any OpenAI-compatible provider works** — just set `MYPROVIDER_API_KEYS=...` and `MYPROVIDER_BASE_URL=https://...`

---

## 🔌 Routing Strategies

```python
from llmcycle.core.router import RoutingStrategy

RoutingStrategy.PRIORITY        # Default: follow your fallback sort order
RoutingStrategy.ROUND_ROBIN     # Cycle across all providers equally
RoutingStrategy.LOWEST_LATENCY  # Always pick the statistically fastest provider
RoutingStrategy.CANARY          # Canary routing with dynamic split percentages
RoutingStrategy.WEIGHTED        # Weight-based traffic routing splits
```

---

## ⚡ Core Enterprise Features (Caching, Rate Limits, Guardrails)

To keep LLMCycle extremely lightweight and fast, all advanced enterprise features are **completely dynamic, self-throttling, and default to `False` / disabled**. You only opt-in and pay the computational cost for exactly what you use.

---

### 1. Pluggable Prompt Caching ♻️
Avoid duplicate LLM costs and reduce latency down to ~10ms for identical repeating queries. 

* **How it works:** Defaults to `False` (no caching). Passing `cache=True` activates the fast `InMemoryCache`. You can also supply a database-backed pluggable cache instance (e.g. `SQLCache` or `RedisCache`).
* **TTL Activation:** Set the exact cache lifetime per-call using `cache_ttl` (in seconds).

```python
from llmcycle import LLMCycle
from llmcycle.core.cache import SQLCache

# Enable default In-Memory Caching
client = LLMCycle(cache=True)

# OR pass a SQL / Redis pluggable cache instance
db_cache = SQLCache("sqlite+aiosqlite:///cache.db")
client = LLMCycle(cache=db_cache)

# Caching is triggered dynamically by passing `cache_ttl`
response1 = await client.complete("openai/gpt-4o-mini", "What is 2+2?", cache_ttl=300)
response2 = await client.complete("openai/gpt-4o-mini", "What is 2+2?", cache_ttl=300) # Served instantly (~1ms) from cache!
```

---

### 2. Client-Side Rate Limiting 🚦
Prevent rate-limit failures (HTTP 429) before they even hit your providers using a high-performance token-bucket rate limiter.

* **How it works:** Defaults to `False` (no rate limits). Pass `rate_limits=True` to activate sensible default limits (60 RPM / 40,000 TPM), or supply a custom dictionary mapping models/providers to specific limits.
* **Fair Queueing:** If a request exceeds RPM or TPM, the rate-limiter automatically pauses and queues execution, waking up exactly when limits replenish.

```python
# Enable sensible default rate limits (60 RPM, 40,000 TPM)
client = LLMCycle(rate_limits=True)

# OR configure precise rate limits per model or provider
client = LLMCycle(
    rate_limits={
        "openai/gpt-4o": {"rpm": 100, "tpm": 80000},
        "groq/llama-3.1-70b": {"rpm": 30, "tpm": 20000},
    }
)
```

---

### 3. PII & Secrets Guardrails 🛡️
Ensure security compliance and prevent data leaks. LLMCycle intercepts outgoing prompts to dynamically detect and mask sensitive information before they leave your servers, and automatically unmasks the output response before returning it to your application.

* **How it works:** Defaults to `False` (no guardrails). Pass `guardrail=True` to enable state-of-the-art PII and high-entropy secret masking.
* **Sensitive Types Masked:** Emails, credit card numbers, Social Security Numbers (SSNs), IP addresses, and high-entropy cloud/API tokens.

```python
# Enable standard PII and Secrets Guardrail
client = LLMCycle(guardrail=True)

# Outgoing prompt is masked to: "My email is [EMAIL_1] and my key is [API_KEY_1]"
# Response is automatically unmasked back to the original values!
response = await client.complete(
    "openai/gpt-4o-mini", 
    "Verify this info: My email is alice@example.com and my API key is sk-1234567890abcdef1234567890abcdef"
)
```

---

### 4. Semantic Caching 🧠
Semantic caching uses TF-IDF + Cosine Similarity to serve cached responses for *conceptually similar* prompts, ignoring minor typos or word reordering.

```python
client = LLMCycle(semantic_cache=True)

# First call hits the LLM
resp1 = await client.complete("openai/gpt-4o", "Explain quantum physics to a 5 year old.")

# Second call is served from Semantic Cache instantly!
resp2 = await client.complete("openai/gpt-4o", "Explain quantum physics to a five yr old.")
```

---

### 5. Shadow Routing (Dark Launching / A/B Testing) 👻
Test new models in production with zero risk. Send production traffic to your primary model, and asynchronously mirror the identical prompt to a "shadow" model in the background.

```python
client = LLMCycle()
resp = await client.complete(
    "openai/gpt-4o",
    "Summarize this meeting.",
    shadow_models=["anthropic/claude-3-5-sonnet", "groq/llama-3.1-70b"]
)
# The user gets the GPT-4o response instantly.
# Claude and Llama process the same request in the background and log it to storage.
```

---

### 6. Prompt Registry & Versioning 📜
Manage versioned prompt templates dynamically.

```python
client = LLMCycle()

client.prompts.set("greeting", "Hello {{name}}, welcome to {{place}}!", version="v1")
client.prompts.set("greeting", "Hey {{name}}, enjoy your stay at {{place}}!", version="v2")

resp = await client.complete(
    "openai/gpt-4o", 
    client.prompts.render("greeting", name="Alice", place="Wonderland", version="v2")
)
```

---

### 7. Cost-Optimized Routing 💸
Automatically route to the cheapest provider.

```python
from llmcycle.core.router import RoutingStrategy

client = LLMCycle(
    strategy=RoutingStrategy.COST_OPTIMIZED,
    fallbacks={
        "openai/gpt-4o-mini": ["anthropic/claude-3-haiku", "groq/llama-3.1-8b"]
    }
)
# Routes to Groq -> OpenAI -> Anthropic (based on known input token costs)
```

---

### 8. Multimodal Attachments 📎

Run multimodal queries with zero-copy or automated cloud offloading. Simply pass PDF, image, audio, or video files into `attachments`.

* **How it works:** Defaults to `local` storage. Saves files to a local directory (for caching/record-keeping) and automatically encodes them as standard Base64 Data URL payloads.
* **AWS S3 Offloading:** Need cloud-based file serving for models that require URL inputs? Switch `attachment_storage` to `"s3"`. Files are automatically uploaded using dynamic `boto3` integration, returning secure, pre-signed URLs valid for 1 hour.

```python
from llmcycle import LLMCycle

# Local attachments storage
client = LLMCycle(
    attachment_storage="local",
    attachment_config={
        "local_dir": "./saved_attachments"  # Where local copies are saved
    }
)

# Call complete or stream with attachments
response = await client.complete(
    model="openai/gpt-4o-mini",
    prompt="Explain the core problem in this document and look at this image.",
    attachments=[
        "./documents/audit_report.pdf",
        "./images/system_architecture.png"
    ]
)
print(response.content)

# AWS S3-backed attachments (zero mandatory external dependencies)
client_s3 = LLMCycle(
    attachment_storage="s3",
    attachment_config={
        "s3_bucket": "my-llmcycle-attachments",
        "s3_prefix": "runs/attachments/",       # Optional, default: "attachments/"
        "s3_region": "us-west-2"                 # Optional, default: "us-east-1"
    }
)
```

---

## 🚀 CLI

```bash
llmcycle providers           # List all loaded providers + key health
llmcycle models              # Fetch and list all dynamic live models across providers in parallel
llmcycle models groq         # Fetch and list live models for a specific provider
llmcycle ui                  # Start dashboard on http://127.0.0.1:8000
```

### Changing the UI port / host

```bash
# Custom port
llmcycle ui --port 9000

# Custom host + port (expose to network)
llmcycle ui --host 0.0.0.0 --port 9000

# Dev mode with auto-reload on code changes
llmcycle ui --port 8080 --reload

# All options
llmcycle ui --help
```

### Via env variables (permanent config)

```env
# .env
LLMCYCLE_UI_HOST=0.0.0.0
LLMCYCLE_UI_PORT=9000
```

Then just run:

```bash
llmcycle ui    # picks up host/port from .env automatically
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
