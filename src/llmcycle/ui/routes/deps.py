import os
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from llmcycle import LLMCycle

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/token")
SESSION_TOKEN = secrets.token_urlsafe(32)
llm_client = LLMCycle()

async def auth(token: str = Depends(oauth2_scheme)):
    if not secrets.compare_digest(token, SESSION_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token", headers={"WWW-Authenticate": "Bearer"})
    return token
