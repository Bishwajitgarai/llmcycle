from typing import List, Dict, Optional
from pydantic import BaseModel

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
