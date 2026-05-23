from fastapi import APIRouter, Depends, Query, HTTPException
from llmcycle.core.router import RoutingStrategy
from .deps import auth, llm_client
from .models import SetFallbackRequest

router = APIRouter()

@router.get("/api/v1/router")
async def get_router(_: str = Depends(auth)):
    return {
        "strategy": llm_client.router.strategy.value,
        "fallbacks": llm_client.router.fallbacks,
        "latencies": llm_client.router.latency.all(),
    }

@router.post("/api/v1/router/fallbacks")
async def set_fallbacks(req: SetFallbackRequest, _: str = Depends(auth)):
    llm_client.router.fallbacks = req.fallbacks
    return {"status": "ok", "fallbacks": req.fallbacks}

@router.put("/api/v1/router/strategy")
async def set_strategy(strategy: str = Query(...), _: str = Depends(auth)):
    try:
        llm_client.router.strategy = RoutingStrategy(strategy)
        return {"status": "ok", "strategy": strategy}
    except ValueError:
        raise HTTPException(400, f"Unknown strategy '{strategy}'. Use: priority, round_robin, lowest_latency")
