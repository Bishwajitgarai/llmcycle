"""
LLMCycle Client - Main Entry Point
====================================
Auto-discovers providers from environment variables.
Pattern: {PROVIDER}_API_KEYS=key1,key2,key3
Optional: {PROVIDER}_BASE_URL=https://custom.endpoint.com/v1
"""
from __future__ import annotations
import asyncio
import os
import logging
from typing import Optional, Dict, List, AsyncGenerator

from dotenv import load_dotenv

from llmcycle.schema import CompletionRequest, CompletionResponse, Message
from llmcycle.core.keys import KeyManager
from llmcycle.core.router import ModelRouter, RoutingStrategy
from llmcycle.core.stream import StreamResilienceManager, RetryPolicy
from llmcycle.providers.openai_compatible import OpenAICompatibleProvider
from llmcycle.providers.registry import PROVIDER_REGISTRY

logger = logging.getLogger(__name__)


class LLMCycle:
    """
    The single interface for all LLM operations.

    Auto-loads providers from .env:
        OPENAI_API_KEYS=sk-1,sk-2
        GROQ_API_KEYS=gsk-abc
        OLLAMA_API_KEYS=local          # no real key needed for Ollama

    Usage:
        client = LLMCycle()
        response = await client.complete("openai/gpt-4o", "Explain RAG in one sentence")
        async for chunk in client.stream("groq/llama-3.1-70b", "Write a poem"):
            print(chunk, end="")
    """

    def __init__(
        self,
        env_path: str = ".env",
        fallbacks: Optional[Dict[str, List[str]]] = None,
        strategy: RoutingStrategy = RoutingStrategy.PRIORITY,
        log_level: str = "WARNING",
    ):
        logging.basicConfig(level=getattr(logging, log_level.upper(), logging.WARNING))
        # Safe BOM-aware .env loader (handles UTF-8, UTF-16, UTF-8-BOM)
        from pathlib import Path as _Path
        env_file = _Path(env_path)
        if env_file.exists():
            for _enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
                try:
                    for _line in env_file.read_text(encoding=_enc).splitlines():
                        _line = _line.strip()
                        if not _line or _line.startswith("#") or "=" not in _line:
                            continue
                        _k, _, _v = _line.partition("=")
                        _k = _k.strip(); _v = _v.strip().strip('"').strip("'")
                        if _k and _k not in os.environ:
                            os.environ[_k] = _v
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

        self.key_manager = KeyManager()
        self._providers: Dict[str, OpenAICompatibleProvider] = {}

        self._auto_load_from_env()

        self.router = ModelRouter(fallbacks=fallbacks or {}, strategy=strategy)
        self._stream_mgr = StreamResilienceManager(self.router, self.key_manager, self._providers)

    # ─── Auto-discovery ──────────────────────────────────────────────────

    def _auto_load_from_env(self):
        """Scan env for *_API_KEYS patterns and register providers."""
        for env_key, env_val in os.environ.items():
            if not env_key.endswith("_API_KEYS"):
                continue
            provider_name = env_key[: -len("_API_KEYS")].upper()
            keys = [k.strip() for k in env_val.split(",") if k.strip()]
            if not keys:
                continue

            # Resolve base URL: explicit override > registry > inferred wildcard
            base_url = (
                os.environ.get(f"{provider_name}_BASE_URL")
                or PROVIDER_REGISTRY.get(provider_name)
                or f"https://api.{provider_name.lower()}.com/v1"
            )

            p_key = provider_name.lower()
            self._providers[p_key] = OpenAICompatibleProvider(base_url, provider_name=p_key)
            self.key_manager.add_keys(p_key, keys)
            logger.info(f"Registered provider [{p_key}] with {len(keys)} key(s) → {base_url}")

    # ─── Provider management ─────────────────────────────────────────────

    def add_provider(self, name: str, api_keys: List[str], base_url: Optional[str] = None):
        """Manually register a provider at runtime (no env required)."""
        p = name.lower()
        url = base_url or PROVIDER_REGISTRY.get(name.upper()) or f"https://api.{p}.com/v1"
        self._providers[p] = OpenAICompatibleProvider(url, provider_name=p)
        self.key_manager.add_keys(p, api_keys)

    def get_providers(self) -> List[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    async def get_models(self, provider: str) -> List[str]:
        """Fetch available models from a provider using a rotated key."""
        p = provider.lower()
        if p not in self._providers:
            return []
        key = self.key_manager.get_next_key(p)
        if not key:
            return []
        return await self._providers[p].get_models(key)

    def get_key_stats(self, provider: str) -> List[dict]:
        """Return per-key health stats for a provider."""
        return self.key_manager.get_stats(provider)

    # ─── Inference ───────────────────────────────────────────────────────

    async def complete(
        self,
        model: str,
        prompt: Optional[str] = None,
        messages: Optional[List[dict]] = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        **kwargs,
    ) -> CompletionResponse:
        """
        One-shot completion with smart retry.

        Args:
            model:       "provider/model-name" or just "model-name"
            prompt:      Convenience shortcut — wraps in user message
            messages:    Full messages list (overrides prompt)
            max_retries: Max total retries across all providers (default: 2).
                         If the current provider has more keys, rotates key
                         immediately (no delay). Otherwise waits retry_delay
                         then tries the next provider in the fallback chain.
            retry_delay: Seconds to wait before switching providers (default: 1.0).
        """
        if messages is None:
            if prompt is None:
                raise ValueError("Provide either 'prompt' or 'messages'.")
            messages = [{"role": "user", "content": prompt}]

        req = CompletionRequest(
            model=model,
            messages=[Message(**m) for m in messages],
            **kwargs,
        )
        policy = RetryPolicy(max_retries=max_retries, retry_delay=retry_delay)
        return await self._stream_mgr.complete(req, retry_policy=policy)

    async def stream(
        self,
        model: str,
        prompt: Optional[str] = None,
        messages: Optional[List[dict]] = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        stop_event: Optional[asyncio.Event] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Resilient streaming with smart retry and mid-stream stop support.

        Args:
            model:       "provider/model-name" or just "model-name"
            prompt:      Convenience shortcut
            messages:    Full messages list (overrides prompt)
            max_retries: Max retries across providers (default: 2).
                         Rotates key immediately if one is available;
                         otherwise waits retry_delay then tries next provider.
            retry_delay: Seconds between provider switches (default: 1.0).
            stop_event:  asyncio.Event — set() it to stop the stream cleanly
                         at the next chunk boundary from any coroutine.

        Usage:
            # Simple
            async for chunk in client.stream("deepseek/deepseek-chat", "Hello!"):
                print(chunk, end="", flush=True)

            # With custom retry
            async for chunk in client.stream("groq/llama-3.1-70b", "Hello!",
                                              max_retries=4, retry_delay=2.0):
                print(chunk, end="", flush=True)

            # Stop mid-stream from outside
            stop = asyncio.Event()
            async for chunk in client.stream("openai/gpt-4o", "Write a novel",
                                              stop_event=stop):
                print(chunk, end="", flush=True)
                if some_condition:
                    stop.set()  # clean stop
        """
        if messages is None:
            if prompt is None:
                raise ValueError("Provide either 'prompt' or 'messages'.")
            messages = [{"role": "user", "content": prompt}]

        req = CompletionRequest(
            model=model,
            messages=[Message(**m) for m in messages],
            stream=True,
            **kwargs,
        )
        policy = RetryPolicy(max_retries=max_retries, retry_delay=retry_delay)
        async for chunk in self._stream_mgr.safe_stream(req, stop_event=stop_event, retry_policy=policy):
            yield chunk
