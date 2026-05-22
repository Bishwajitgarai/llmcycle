"""
Storage data models — Pydantic v2.
Entities: Workplace → Team → User → Session → Request → History
"""
from __future__ import annotations
import time
import uuid
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


def _uid() -> str:
    return str(uuid.uuid4())

def _now() -> float:
    return time.time()


class Workplace(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str
    settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Team(BaseModel):
    id: str = Field(default_factory=_uid)
    name: str
    workplace_id: str
    member_ids: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class User(BaseModel):
    id: str = Field(default_factory=_uid)
    username: str
    email: Optional[str] = None
    role: str = "member"           # "admin" | "member" | "viewer"
    team_id: Optional[str] = None
    workplace_id: Optional[str] = None
    hashed_password: Optional[str] = None
    created_at: float = Field(default_factory=_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Session(BaseModel):
    id: str = Field(default_factory=_uid)
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    model: str = ""
    started_at: float = Field(default_factory=_now)
    ended_at: Optional[float] = None
    total_requests: int = 0
    total_tokens: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMRequest(BaseModel):
    id: str = Field(default_factory=_uid)
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    model: str
    provider: str
    prompt: str = ""
    response: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    status: str = "success"        # "success" | "error" | "fallback"
    error: Optional[str] = None
    fallback_used: bool = False
    retries: int = 0
    created_at: float = Field(default_factory=_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HistoryMessage(BaseModel):
    id: str = Field(default_factory=_uid)
    session_id: str
    request_id: Optional[str] = None
    role: str                       # "user" | "assistant" | "system"
    content: str
    created_at: float = Field(default_factory=_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
