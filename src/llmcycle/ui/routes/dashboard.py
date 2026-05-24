from fastapi import APIRouter, Depends, HTTPException
import os
from .deps import auth, llm_client
from .models import GroupRequest, ProxyRequest

router = APIRouter()

@router.get("/api/v1/dashboard")
async def dashboard(_: str = Depends(auth)):
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
        "total_active_keys": sum(llm_client.key_manager.key_count(p)["active"] for p in llm_client.get_providers()),
    }

@router.get("/api/v1/system")
async def get_system_status(_: str = Depends(auth)):
    return {
        "storage": llm_client.storage.__class__.__name__ if llm_client.storage else "MemoryStorage",
        "config_loader": "env",
        "semantic_cache": getattr(llm_client, "_semantic_cache", None) is not None,
    }

@router.get("/api/v1/proxy")
async def get_proxy(_: str = Depends(auth)):
    return {"proxy": llm_client.proxy}

@router.post("/api/v1/proxy")
async def set_proxy(req: ProxyRequest, _: str = Depends(auth)):
    proxy_val = req.proxy.strip() if req.proxy else None
    if not proxy_val:
        proxy_val = None
    
    # Update the proxy on the client
    llm_client.proxy = proxy_val
    
    # Update the proxy on all currently initialized providers
    for provider in llm_client._providers.values():
        provider.proxy = proxy_val
        
    return {"status": "ok", "proxy": proxy_val}

@router.get("/api/v1/groups")
async def get_groups(_: str = Depends(auth)):
    groups_out = []
    for g_id, models in llm_client.router.groups.list_all().items():
        groups_out.append({
            "id": g_id,
            "models": models,
            "strategy": None,
        })
    return groups_out

@router.post("/api/v1/groups")
async def set_group(req: GroupRequest, _: str = Depends(auth)):
    await llm_client.router.groups.set_async(req.name, req.models)
    return {"status": "ok", "group": req.name, "models": req.models}

@router.delete("/api/v1/groups/{name}")
async def delete_group(name: str, _: str = Depends(auth)):
    removed = await llm_client.router.groups.remove_async(name)
    if not removed:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"status": "ok", "message": f"Group {name} removed"}

@router.get("/api/v1/detected_env_providers")
async def get_detected_env_providers(_: str = Depends(auth)):
    detected = []
    for k in os.environ.keys():
        if k.endswith("_API_KEYS"):
            prov = k[:-9].lower()
            if prov not in detected:
                detected.append(prov)
    return {"detected": detected}

@router.post("/api/v1/providers/auto_register")
async def auto_register_env_providers(_: str = Depends(auth)):
    llm_client._auto_load_configs()
    return {"status": "ok", "providers": llm_client.get_providers()}

# ─── Analytics endpoints ───────────────────────────────────────────────────────
@router.get("/api/v1/analytics/data")
async def get_analytics_data(_: str = Depends(auth)):
    if not llm_client.storage or not getattr(llm_client.storage, "analytics", None):
        return {
            "summary": {"total_requests": 0, "success_count": 0, "error_count": 0},
            "by_provider": [],
            "by_model": [],
            "timeseries": [],
            "top_errors": []
        }
    
    engine = llm_client.storage.analytics
    # Fetch most recent 2,000 requests to guarantee high speed and avoid database timeouts
    reqs = await engine._fetch(limit=2000)
    
    if not reqs:
        return {
            "summary": {"total_requests": 0, "success_count": 0, "error_count": 0},
            "by_provider": [],
            "by_model": [],
            "timeseries": [],
            "top_errors": []
        }
        
    summary = engine._compute_summary(reqs, from_ts=None, to_ts=None)
    
    # Providers breakdown
    prov_groups = {}
    for r in reqs:
        prov_groups.setdefault(r.provider, []).append(r)
    by_provider = []
    for prov, rs in sorted(prov_groups.items(), key=lambda x: -len(x[1])):
        lats = [r.latency_ms for r in rs]
        by_provider.append({
            "provider": prov,
            "requests": len(rs),
            "tokens": sum(r.prompt_tokens + r.completion_tokens for r in rs),
            "avg_latency_ms": round(sum(lats) / len(lats), 2),
            "errors": sum(1 for r in rs if r.status == "error"),
        })
        
    # Models breakdown
    model_groups = {}
    for r in reqs:
        model_groups.setdefault(r.model, []).append(r)
    by_model = []
    for m, rs in sorted(model_groups.items(), key=lambda x: -len(x[1])):
        by_model.append({
            "model": m,
            "requests": len(rs),
            "tokens": sum(r.prompt_tokens + r.completion_tokens for r in rs),
            "avg_latency_ms": round(sum(r.latency_ms for r in rs) / len(rs), 2),
        })
        
    # Timeseries
    import datetime
    time_groups = {}
    for r in reqs:
        key = datetime.datetime.utcfromtimestamp(r.created_at).strftime("%Y-%m-%dT%H:00")
        time_groups.setdefault(key, []).append(r)
    timeseries = []
    for k, rs in sorted(time_groups.items()):
        timeseries.append({
            "bucket": k,
            "requests": len(rs),
            "tokens": sum(r.prompt_tokens + r.completion_tokens for r in rs),
            "avg_latency_ms": round(sum(r.latency_ms for r in rs) / len(rs), 2),
        })
        
    # Top errors
    errors_list = [r for r in reqs if r.status == "error" and r.error]
    error_counts = {}
    for r in errors_list:
        error_counts[r.error] = error_counts.get(r.error, 0) + 1
    top_errors = [
        {"error": e, "count": c, "provider": next((r.provider for r in errors_list if r.error == e), "?")}
        for e, c in sorted(error_counts.items(), key=lambda x: -x[1])[:10]
    ]
    
    return {
        "summary": summary,
        "by_provider": by_provider,
        "by_model": by_model,
        "timeseries": timeseries,
        "top_errors": top_errors
    }
