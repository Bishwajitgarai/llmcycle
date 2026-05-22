from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Message(BaseModel):
    role: str
    content: str

class CompletionRequest(BaseModel):
    messages: List[Message]
    model: str
    stream: bool = False
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    
class APIKeyStats(BaseModel):
    key_hash: str
    rate_limit_remaining: int = Field(default=99999)
    last_used: float = Field(default=0.0)
    is_active: bool = Field(default=True)
