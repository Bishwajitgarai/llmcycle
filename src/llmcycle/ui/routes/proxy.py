import json
import secrets
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from .deps import llm_client
from .constants import PRIMARY_MODELS

router = APIRouter()

@router.post("/v1/chat/completions")
async def openai_proxy_chat_completions(req: Dict[str, Any]):
    model = req.get("model")
    if not model:
        raise HTTPException(400, "Missing 'model' field")
    
    messages = req.get("messages", [])
    stream = req.get("stream", False)
    
    gen_kwargs = {}
    for k in ("temperature", "max_tokens", "top_p", "presence_penalty", "frequency_penalty", "stop"):
        if k in req:
            gen_kwargs[k] = req[k]
            
    if stream:
        async def event_generator():
            try:
                import time
                chunk_id = f"chatcmpl-{secrets.token_hex(12)}"
                created_ts = int(time.time())
                
                async for text in llm_client.stream(model=model, messages=messages, **gen_kwargs):
                    chunk = {
                        "id": chunk_id, "object": "chat.completion.chunk",
                        "created": created_ts, "model": model,
                        "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                
                final_chunk = {
                    "id": chunk_id, "object": "chat.completion.chunk",
                    "created": created_ts, "model": model,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                err_chunk = {
                    "id": "err", "object": "chat.completion.chunk",
                    "created": int(time.time()), "model": model,
                    "choices": [{"index": 0, "delta": {"content": f"\n\n[LLMCycle Proxy Error]: {str(e)}"}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(err_chunk)}\n\n"
                yield "data: [DONE]\n\n"
        
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        try:
            resp = await llm_client.complete(model=model, messages=messages, **gen_kwargs)
            import time
            return {
                "id": resp.id or f"chatcmpl-{secrets.token_hex(12)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": resp.model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": resp.content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens, "total_tokens": resp.prompt_tokens + resp.completion_tokens}
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/v1/models")
async def list_models_openai():
    all_models = []
    providers = llm_client.get_providers()
    if not providers:
        providers = list(PRIMARY_MODELS.keys())
        
    for p in providers:
        p_lower = p.lower()
        models = []
        try:
            models = await llm_client.get_models(p_lower)
        except Exception:
            pass
        if not models:
            models = PRIMARY_MODELS.get(p_lower, ["default-model"])
        for m in models:
            all_models.append({
                "id": f"{p_lower}/{m}",
                "object": "model",
                "created": 1677858200,
                "owned_by": p_lower
            })
    return {"object": "list", "data": all_models}
