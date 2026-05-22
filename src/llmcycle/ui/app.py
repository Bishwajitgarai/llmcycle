"""
LLMCycle Dashboard API
========================
Fully dynamic REST API with token auth.
All state is managed in memory on the running LLMCycle client instance.
"""
import os
import secrets
import asyncio
from typing import List, Dict, Optional, Any
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from llmcycle import LLMCycle
from llmcycle.core.router import RoutingStrategy

# ─── App setup ───────────────────────────────────────────────────────────────
app = FastAPI(title="LLMCycle Dashboard API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")
SESSION_TOKEN = secrets.token_urlsafe(32)

BASE_DIR = Path(__file__).resolve().parent
templates_dir = BASE_DIR / "templates"

# Global client instance (auto-loads from .env)
llm_client = LLMCycle()

PRIMARY_MODELS: Dict[str, List[str]] = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    "anthropic": ["claude-3-5-sonnet", "claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    "google": ["gemini-1.5-pro", "gemini-1.5-flash"],
    "deepseek": ["deepseek-chat", "deepseek-coder"],
    "groq": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
    "together": [
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "mistralai/Mixtral-8x7B-Instruct-v0.1"
    ],
    "ollama": ["llama3", "mistral", "phi3", "gemma"],
    "lm_studio": ["local-model"],
    "vllm": ["local-model"],
    "openrouter": ["meta-llama/llama-3.1-70b-instruct", "google/gemini-flash-1.5", "openai/gpt-4o-mini"],
}

# ─── Pydantic models ─────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class AddProviderRequest(BaseModel):
    name: str
    api_keys: List[str]
    base_url: Optional[str] = None

class AddKeyRequest(BaseModel):
    keys: List[str]

class SetFallbackRequest(BaseModel):
    fallbacks: Dict[str, List[str]]

class TestCompleteRequest(BaseModel):
    model: str
    prompt: str
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512
    max_retries: Optional[int] = 2
    retry_delay: Optional[float] = 1.0

# ─── Auth ─────────────────────────────────────────────────────────────────────
@app.post("/api/token", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    correct_user = os.environ.get("LLMCYCLE_USER_ADMIN", "admin")
    correct_pass = os.environ.get("LLMCYCLE_USER_ADMIN_PAASWORD", "admin")
    if not (
        secrets.compare_digest(form_data.username, correct_user) and
        secrets.compare_digest(form_data.password, correct_pass)
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    return TokenResponse(access_token=SESSION_TOKEN, token_type="bearer")

async def auth(token: str = Depends(oauth2_scheme)):
    if not secrets.compare_digest(token, SESSION_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token",
                            headers={"WWW-Authenticate": "Bearer"})
    return token

# ─── Dashboard overview ───────────────────────────────────────────────────────
@app.get("/api/dashboard")
async def dashboard(_: str = Depends(auth)):
    """Full dashboard snapshot: providers, keys, fallbacks, latency."""
    providers_out = []
    for name in llm_client.get_providers():
        counts = llm_client.key_manager.key_count(name)
        key_stats = llm_client.key_manager.get_stats(name)
        latency = llm_client.router.latency.get(name)
        providers_out.append({
            "name": name,
            "base_url": llm_client._providers[name].base_url,
            "keys": counts,
            "key_stats": key_stats,
            "latency_ms": round(latency, 1) if latency < 999999 else None,
        })

    return {
        "providers": providers_out,
        "fallbacks": llm_client.router.fallbacks,
        "strategy": llm_client.router.strategy.value,
        "total_providers": len(providers_out),
        "total_active_keys": sum(
            llm_client.key_manager.key_count(p)["active"]
            for p in llm_client.get_providers()
        ),
    }

# ─── Providers ────────────────────────────────────────────────────────────────
@app.get("/api/providers")
async def list_providers(_: str = Depends(auth)):
    result = []
    for name in llm_client.get_providers():
        counts = llm_client.key_manager.key_count(name)
        result.append({
            "name": name,
            "base_url": llm_client._providers[name].base_url,
            "keys": counts,
        })
    return result

@app.post("/api/providers")
async def add_provider(req: AddProviderRequest, _: str = Depends(auth)):
    """Dynamically add a new provider with keys at runtime."""
    llm_client.add_provider(req.name, req.api_keys, req.base_url)
    return {"status": "ok", "provider": req.name.lower(), "keys_added": len(req.api_keys)}

@app.get("/api/providers/{name}/models")
async def get_provider_models(name: str, _: str = Depends(auth)):
    """Fetch the model list from a provider, falling back to primary models if empty or failing."""
    p_lower = name.lower()
    models = []
    try:
        models = await llm_client.get_models(p_lower)
    except Exception:
        pass
    if not models:
        models = PRIMARY_MODELS.get(p_lower, ["default-model"])
    return {"provider": name, "models": models, "count": len(models)}

@app.get("/api/active_models")
async def get_active_models(_: str = Depends(auth)):
    """Get all active/available models grouped by provider with a fallback to primary/default models."""
    out = {}
    for p in llm_client.get_providers():
        p_lower = p.lower()
        models = []
        try:
            models = await llm_client.get_models(p_lower)
        except Exception:
            pass
        if not models:
            models = PRIMARY_MODELS.get(p_lower, ["default-model"])
        out[p] = models
    return out

@app.get("/api/providers/{name}/keys")
async def get_provider_keys(name: str, _: str = Depends(auth)):
    return {"provider": name, "stats": llm_client.key_manager.get_stats(name)}

@app.post("/api/providers/{name}/keys")
async def add_keys(name: str, req: AddKeyRequest, _: str = Depends(auth)):
    """Add more API keys to an existing provider at runtime."""
    for k in req.keys:
        llm_client.key_manager.add_key(name, k)
    return {"status": "ok", "provider": name, "keys_added": len(req.keys)}

# ─── Routing ─────────────────────────────────────────────────────────────────
@app.get("/api/router")
async def get_router(_: str = Depends(auth)):
    return {
        "strategy": llm_client.router.strategy.value,
        "fallbacks": llm_client.router.fallbacks,
        "latencies": llm_client.router.latency.all(),
    }

@app.post("/api/router/fallbacks")
async def set_fallbacks(req: SetFallbackRequest, _: str = Depends(auth)):
    """Dynamically update the fallback routing config."""
    llm_client.router.fallbacks = req.fallbacks
    return {"status": "ok", "fallbacks": req.fallbacks}

@app.put("/api/router/strategy")
async def set_strategy(strategy: str = Query(...), _: str = Depends(auth)):
    """Change routing strategy: priority | round_robin | lowest_latency"""
    try:
        llm_client.router.strategy = RoutingStrategy(strategy)
        return {"status": "ok", "strategy": strategy}
    except ValueError:
        raise HTTPException(400, f"Unknown strategy '{strategy}'. Use: priority, round_robin, lowest_latency")

# ─── Test completion ──────────────────────────────────────────────────────────
@app.post("/api/complete")
async def test_complete(req: TestCompleteRequest, _: str = Depends(auth)):
    """Test a non-streaming completion through the router."""
    try:
        resp = await llm_client.complete(
            model=req.model,
            prompt=req.prompt,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            max_retries=req.max_retries,
            retry_delay=req.retry_delay,
        )
        return {
            "content": resp.content,
            "provider": resp.provider,
            "model": resp.model,
            "latency_ms": round(resp.latency_ms, 1),
            "tokens": {"prompt": resp.prompt_tokens, "completion": resp.completion_tokens},
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/stream")
async def test_stream(
    model: str = Query(...),
    prompt: str = Query(...),
    max_retries: int = Query(2),
    retry_delay: float = Query(1.0),
    _: str = Depends(auth),
):
    """SSE streaming endpoint for the test console in the UI."""
    async def event_generator():
        try:
            async for chunk in llm_client.stream(
                model=model,
                prompt=prompt,
                max_retries=max_retries,
                retry_delay=retry_delay,
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ─── Registry ─────────────────────────────────────────────────────────────────
@app.get("/api/registry")
async def get_registry(_: str = Depends(auth)):
    """Return the full built-in provider registry."""
    from llmcycle.providers.registry import PROVIDER_REGISTRY
    return PROVIDER_REGISTRY

# ─── Serve SPA ───────────────────────────────────────────────────────────────
@app.get("/")
async def serve_ui():
    return FileResponse(templates_dir / "dashboard.html")
