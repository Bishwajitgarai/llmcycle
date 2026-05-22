"""
Production schema models with Pydantic v2.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field
import time

class Message(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]

class CompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop: Optional[Union[str, List[str]]] = None
    extra: Optional[Dict[str, Any]] = None

    def to_api_dict(self) -> dict:
        """Serialize for sending to OpenAI-compatible API."""
        d = self.model_dump(exclude_none=True, exclude={"extra"})
        d["messages"] = [m.model_dump() for m in self.messages]
        if self.extra:
            d.update(self.extra)
        return d

class CompletionResponse(BaseModel):
    id: str
    model: str
    provider: str
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    created_at: float = Field(default_factory=time.time)

class StreamChunk(BaseModel):
    content: str
    model: str
    provider: str
    done: bool = False
