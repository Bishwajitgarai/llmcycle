import os
import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any
from llmcycle import LLMCycle
from pathlib import Path

app = FastAPI(title="LLMCycle API Dashboard")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")

# Static token for simplicity in this MVP. For prod, use JWTs.
SESSION_TOKEN = secrets.token_urlsafe(32)

# Path to templates/static
BASE_DIR = Path(__file__).resolve().parent
templates_dir = BASE_DIR / "templates"

# Global Client Instance
llm_client = LLMCycle()

# Models
class ProviderInfo(BaseModel):
    name: str
    base_url: str
    total_keys: int
    active_keys: int

class DashboardData(BaseModel):
    providers: List[ProviderInfo]
    fallbacks: Dict[str, List[str]]

@app.post("/api/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    correct_username = os.environ.get("LLMCYCLE_USER_ADMIN", "admin")
    correct_password = os.environ.get("LLMCYCLE_USER_ADMIN_PAASWORD", "admin")
    
    if not (secrets.compare_digest(form_data.username, correct_username) and 
            secrets.compare_digest(form_data.password, correct_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {"access_token": SESSION_TOKEN, "token_type": "bearer"}

async def verify_token(token: str = Depends(oauth2_scheme)):
    if not secrets.compare_digest(token, SESSION_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

@app.get("/api/dashboard", response_model=DashboardData)
async def get_dashboard_data(token: str = Depends(verify_token)):
    """Protected API endpoint returning all dashboard data as JSON."""
    providers = llm_client.get_available_providers()
    
    provider_details = []
    for p in providers:
        keys_list = llm_client.key_manager._keys.get(p, [])
        active_keys = 0
        for k in keys_list:
            stats = llm_client.key_manager._stats.get(k)
            if stats and stats.is_active:
                active_keys += 1
                
        provider_details.append(ProviderInfo(
            name=p.upper(),
            base_url=llm_client.providers[p].base_url,
            total_keys=len(keys_list),
            active_keys=active_keys
        ))
        
    fallbacks = llm_client.router.strategy.fallbacks if hasattr(llm_client.router.strategy, 'fallbacks') else {}
    
    return DashboardData(providers=provider_details, fallbacks=fallbacks)

@app.get("/")
async def serve_ui():
    """Serve the static HTML frontend."""
    return FileResponse(templates_dir / "dashboard.html")
