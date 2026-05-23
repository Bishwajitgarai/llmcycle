from fastapi import APIRouter, Depends
from .deps import auth, llm_client
from .models import AddProviderRequest, AddKeyRequest
from .constants import PRIMARY_MODELS

router = APIRouter()

@router.get("/api/v1/providers")
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

@router.post("/api/v1/providers")
async def add_provider(req: AddProviderRequest, _: str = Depends(auth)):
    llm_client.add_provider(req.name, req.api_keys, req.base_url)
    return {"status": "ok", "provider": req.name.lower(), "keys_added": len(req.api_keys)}

@router.get("/api/v1/providers/{name}/models")
async def get_provider_models(name: str, _: str = Depends(auth)):
    p_lower = name.lower()
    models = []
    try:
        models = await llm_client.get_models(p_lower)
    except Exception:
        pass
    if not models:
        models = PRIMARY_MODELS.get(p_lower, ["default-model"])
    return {"provider": name, "models": models, "count": len(models)}

@router.get("/api/v1/active_models")
async def get_active_models(_: str = Depends(auth)):
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

@router.get("/api/v1/providers/{name}/keys")
async def get_provider_keys(name: str, _: str = Depends(auth)):
    return {"provider": name, "stats": llm_client.key_manager.get_stats(name)}

@router.post("/api/v1/providers/{name}/keys")
async def add_keys(name: str, req: AddKeyRequest, _: str = Depends(auth)):
    for k in req.keys:
        llm_client.key_manager.add_key(name, k)
    return {"status": "ok", "provider": name, "keys_added": len(req.keys)}

@router.get("/api/v1/registry")
async def get_registry(_: str = Depends(auth)):
    from llmcycle.providers.registry import PROVIDER_REGISTRY
    return PROVIDER_REGISTRY
