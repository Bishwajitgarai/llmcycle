from fastapi import APIRouter, Depends
from .deps import auth, llm_client

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
        "storage": llm_client.storage.__class__.__name__,
        "config_loader": "env",
        "semantic_cache": llm_client.router.semantic_cache is not None,
    }

@router.get("/api/v1/groups")
async def get_groups(_: str = Depends(auth)):
    groups_out = []
    for g_id, g in llm_client.router.groups.items():
        groups_out.append({
            "id": g_id,
            "models": g.models,
            "strategy": g.strategy.value if g.strategy else None,
        })
    return groups_out
