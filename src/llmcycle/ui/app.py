"""
LLMCycle Dashboard API
========================
Fully dynamic REST API with token auth.
All state is managed in memory on the running LLMCycle client instance.
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from .routes import router as api_router

# ─── App setup ───────────────────────────────────────────────────────────────
app = FastAPI(title="LLMCycle Dashboard API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
templates_dir = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

app.include_router(api_router)

# ─── Serve SPA ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    return templates.TemplateResponse("base.html", {"request": request})
