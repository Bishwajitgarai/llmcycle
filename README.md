# LLMCycle ♻️ — The Production-Grade Universal LLM Router

[![PyPI Version](https://img.shields.io/pypi/v/llmcycle.svg)](https://pypi.org/project/llmcycle/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub](https://img.shields.io/badge/GitHub-llmcycle-181717?logo=github)](https://github.com/Bishwajitgarai/llmcycle)

> 📦 **PyPI**: [pypi.org/project/llmcycle](https://pypi.org/project/llmcycle/) &nbsp;|&nbsp; 🐙 **GitHub**: [github.com/Bishwajitgarai/llmcycle](https://github.com/Bishwajitgarai/llmcycle)


**LLMCycle** is an enterprise-grade, zero-dependency universal LLM routing framework.  
Route across **70+ providers**, rotate **unlimited API keys**, handle **every 4xx/5xx error gracefully**, and stream with **zero interruptions** — even if your provider dies mid-response.

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
