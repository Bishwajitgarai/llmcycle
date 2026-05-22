"""
OpenAI-Compatible Provider
===========================
Handles all REST-based providers using the OpenAI chat/completions API spec.
Implements full error classification (400/401/402/429/5xx) mapped to
LLMCycle exception types so the router knows exactly how to react.
"""
from __future__ import annotations
import json
import time
import logging
from typing import AsyncGenerator

import httpx

from llmcycle.schema import CompletionRequest, CompletionResponse
from llmcycle.providers.base import LLMProvider
from llmcycle.providers.cache import get_model_info_cache
from llmcycle.core.errors import classify_http_error, ContentPolicyError

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)


class OpenAICompatibleProvider(LLMProvider):
    """
    Universal OpenAI-compatible HTTP provider.
    Works with: OpenAI, DeepSeek, Groq, Mistral, Together, Fireworks,
    Perplexity, OpenRouter, Anthropic (via compat layer), and 40+ more.
    """

    def __init__(self, base_url: str, provider_name: str = "unknown"):
        self.base_url = base_url.rstrip("/")
        self.provider_name = provider_name
        # Shared LRU + disk cache (singleton across all provider instances)
        self._cache = get_model_info_cache()

    def _headers(self, api_key: str) -> dict:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def get_models(self, api_key: str) -> list[str]:
        """Return sorted list of available model IDs from the provider."""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(api_key),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "data" in data:
                        return sorted(m["id"] for m in data["data"])
                    if "models" in data:
                        return sorted(m.get("id", m) for m in data["models"])
                logger.warning(f"[{self.provider_name}] /models returned {resp.status_code}")
                return []
            except Exception as e:
                logger.debug(f"[{self.provider_name}] get_models failed: {e}")
                return []

    async def get_model_info(self, model_id: str, api_key: str) -> dict:
        """
        Fetch live metadata for a single model — called at most ONCE per model
        across the entire process lifetime (and across restarts via disk cache).

        Cache hierarchy:
          L1  In-memory LRU   — instant, zero I/O
          L2  Disk / SSD      — survives process restart, loaded on first access
          L3  Provider API    — only hit on an absolute cache miss

        Normalised fields returned:
          context_window   — max context tokens
          pricing          — {"input": USD/1K, "output": USD/1K}
          id               — model identifier

        Returns {} if no metadata is available (non-fatal).
        """
        cache_key = f"{self.provider_name}/{model_id}"

        # ── L1 + L2 hit (LRU memory or disk) ────────────────────────────────────
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        info: dict = {}

        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            # Strategy 1: GET /models/{model_id}  (OpenAI, Groq, Together …)
            try:
                resp = await client.get(
                    f"{self.base_url}/models/{model_id}",
                    headers=self._headers(api_key),
                )
                if resp.status_code == 200:
                    info = resp.json()
            except Exception as e:
                logger.debug(
                    f"[{self.provider_name}] GET /models/{model_id} failed: {e}"
                )

            # Strategy 2: scan full /models list (fallback for providers that
            # don't support /models/{id} but embed metadata in the list)
            if not info:
                try:
                    resp = await client.get(
                        f"{self.base_url}/models",
                        headers=self._headers(api_key),
                    )
                    if resp.status_code == 200:
                        raw = resp.json()
                        items = raw.get("data") or raw.get("models") or []
                        for m in items:
                            if isinstance(m, dict) and m.get("id") == model_id:
                                info = m
                                break
                except Exception as e:
                    logger.debug(
                        f"[{self.provider_name}] GET /models list scan failed: {e}"
                    )

        # ── Normalise context window aliases → context_window ────────────────────
        for alias in ("context_length", "max_context_length", "max_tokens", "n_ctx"):
            if alias in info and "context_window" not in info:
                info["context_window"] = info[alias]
                break

        # ── Normalise pricing → {input, output} USD per 1K tokens ─────────────
        raw_pricing = info.get("pricing", {})
        if raw_pricing and "input" not in raw_pricing:
            p_in  = (raw_pricing.get("prompt")     or raw_pricing.get("input")
                     or raw_pricing.get("input_cost_per_token"))
            p_out = (raw_pricing.get("completion") or raw_pricing.get("output")
                     or raw_pricing.get("output_cost_per_token"))
            if p_in is not None and p_out is not None:
                try:
                    info["pricing"] = {
                        "input":  float(p_in)  * 1000,   # per-token → per-1K
                        "output": float(p_out) * 1000,
                    }
                except (TypeError, ValueError):
                    pass

        # ── Write to L1 LRU + L2 disk ──────────────────────────────────────────
        self._cache.set(cache_key, info)
        logger.debug(
            f"[{self.provider_name}] model info cached for '{model_id}': "
            f"ctx={info.get('context_window')} pricing={info.get('pricing')}"
        )
        return info

    async def generate(self, request: CompletionRequest, api_key: str) -> CompletionResponse:
        payload = request.to_api_dict()
        payload["stream"] = False

        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(api_key),
                    json=payload,
                )
            except httpx.ConnectError as e:
                raise classify_http_error(503, str(e), self.provider_name, request.model)
            except httpx.TimeoutException as e:
                raise classify_http_error(504, str(e), self.provider_name, request.model)

            latency_ms = (time.monotonic() - t0) * 1000

            if resp.status_code != 200:
                raise classify_http_error(resp.status_code, resp.text, self.provider_name, request.model)

            data = resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})

            return CompletionResponse(
                id=data.get("id", ""),
                model=data.get("model", request.model),
                provider=self.provider_name,
                content=choice["message"]["content"],
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                latency_ms=latency_ms,
            )

    async def generate_stream(self, request: CompletionRequest, api_key: str) -> AsyncGenerator[str, None]:
        payload = request.to_api_dict()
        payload["stream"] = True

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(api_key),
                    json=payload,
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise classify_http_error(resp.status_code, body.decode(), self.provider_name, request.model)

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            text = delta.get("content")
                            if text:
                                yield text
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

            except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
                raise classify_http_error(503, str(e), self.provider_name, request.model)
            except httpx.TimeoutException as e:
                raise classify_http_error(504, str(e), self.provider_name, request.model)
