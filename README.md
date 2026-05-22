# LLMCycle ♻️

An enterprise-grade, highly resilient LLM management and routing framework. Designed to be **better than LiteLLM** with advanced multi-key support, customized routing (sort order), robust mid-stream error failovers, and a premium **Web Dashboard**.

## 🚀 Key Features

*   **🔑 Universal Provider Support**: Supports *any* provider on the market instantly. Just add `<PROVIDER_NAME>_API_KEYS` to your `.env`!
*   **⚖️ Auto Load-Balancing**: Load multiple API keys for the same provider simply by comma-separating them in your `.env`. LLMCycle automatically round-robins across them and tracks rate limits locally.
*   **🛣️ Custom Fallback Routing**: Configure custom routing. If a primary provider fails, it automatically falls back to your configured secondary.
*   **🛡️ Streaming Time Resilience**: If an LLM disconnects *while streaming a response*, LLMCycle captures the generated text, silently switches to your fallback model, and resumes the stream seamlessly. The client never notices!
*   **🖥️ Premium Web Dashboard**: Manage and view your keys, active providers, and fallback routes through a beautifully designed, secure UI.

## 📦 Installation

```bash
uv add llmcycle
uv add python-dotenv httpx fastapi uvicorn jinja2 python-multipart
```

## ⚙️ Configuration (`.env`)

Drop your keys into a `.env` file. To use multiple keys for load balancing, just separate them with commas!

```env
DEEPSEEK_API_KEYS=sk-deepseek-1,sk-deepseek-2
OPENAI_API_KEYS=sk-openai-primary
TOGETHER_API_KEYS=sk-together-1

# You can even use completely custom providers!
# LLMCycle will default the base URL to https://api.mycustomai.com/v1
MYCUSTOMAI_API_KEYS=sk-custom
# Or explicitly define the base URL for custom providers
OLLAMA_API_KEYS=local
OLLAMA_BASE_URL=http://localhost:11434/v1

# UI Dashboard Auth
LLMCYCLE_USER_ADMIN=admin
LLMCYCLE_USER_ADMIN_PAASWORD=admin
```

## 🖥️ Starting the Web Dashboard

We built a gorgeous, premium Glassmorphism dashboard to monitor your providers.

```bash
# Make sure your PYTHONPATH is set if running from source:
# Windows: $env:PYTHONPATH="src"
# Linux/Mac: export PYTHONPATH="src"

uv run llmcycle ui
```
*Navigate to `http://127.0.0.1:8000` and login with the credentials defined in your `.env`!*

## 💻 Usage: Everything in One!

```python
import asyncio
from llmcycle import LLMCycle

async def main():
    # 1. Initialization (Auto-loads all providers & keys from .env)
    client = LLMCycle(
        env_path=".env",
        custom_fallbacks={
            "deepseek": ["openai", "together"] # Sort order / Fallback chain
        }
    )
    
    # 2. List all dynamically loaded providers
    providers = client.get_available_providers()
    print("Loaded Providers:", providers) 
    
    # 3. Query models supported by a provider
    models = await client.get_provider_models("deepseek")
    print("DeepSeek Models:", models)

if __name__ == "__main__":
    asyncio.run(main())
```

## 🔌 Massive Universal Provider Registry

LLMCycle is pre-configured with base URLs for the most popular platforms:
`OPENAI`, `DEEPSEEK`, `ANTHROPIC`, `TOGETHER`, `GROQ`, `MISTRAL`, `PERPLEXITY`, `ANYSCALE`, `FIREWORKS`, `COHERE`, `DATABRICKS`, `HUGGINGFACE`.

**Wildcard Support:** If you type `RANDOM_API_KEYS`, LLMCycle will automatically assume `https://api.random.com/v1`. If that's wrong, just define `RANDOM_BASE_URL` in your `.env`!
