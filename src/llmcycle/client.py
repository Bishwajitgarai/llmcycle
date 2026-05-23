"""
LLMCycle Client - All-in-One LLM Interface
============================================
Features:
  - Auto-discovers providers from .env (*_API_KEYS pattern)
  - Multi-key rotation with per-key health tracking
  - Smart routing: Priority / Round-Robin / Lowest-Latency / Cost-Optimized
  - Resilient streaming with mid-stream failover
  - Timeout + cancellation tracking (status: success/error/cancelled/timeout)
  - Auto-save to storage with session/user/team/tags
  - Model aliases (map "fast" → "groq/llama-3-70b")
  - Prompt caching (in-memory / semantic similarity with TTL)
  - Structured output (tool-calling API by default, JSON-prompt fallback)
  - Agentic tool-calling loop with max_tool_calls guard
  - Budget enforcement (raises BudgetExceededError if cost_usd exceeded)
  - Context window auto-trim (truncate messages to fit model limits)
  - Request/response middleware hooks (on_before / on_after / on_trace)
  - Parallel batch completions with concurrency control
  - Prompt injection & jailbreak guard (InjectionGuard)
  - Shadow routing / dark launching (shadow_models on complete)
  - Response validation with auto-retry (validators on complete)
  - Prompt registry with versioned templates (PromptRegistry)
  - Semantic caching (TF-IDF cosine similarity)
  - Secret manager adapters (Env / AWS / GCP / Vault)
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import os
import time as _time
from typing import (
    Any, AsyncGenerator, Callable, Dict, List, Optional, Type, TypeVar, Union
)

from dotenv import load_dotenv

from llmcycle.schema import CompletionRequest, CompletionResponse, Message
from llmcycle.core.keys import KeyManager
from llmcycle.core.cache import BaseCache, InMemoryCache
from llmcycle.core.router import ModelRouter, RoutingStrategy
from llmcycle.core.stream import StreamResilienceManager, RetryPolicy
from llmcycle.core.errors import (
    MaxToolCallsExceededError, BudgetExceededError,
    StructuredOutputError,
)
from llmcycle.core.injection import InjectionGuard, InjectionBlockedError
from llmcycle.core.prompts import PromptRegistry
from llmcycle.core.semantic_cache import SemanticCache
from llmcycle.core.groups import GroupManager
from llmcycle.providers.openai_compatible import OpenAICompatibleProvider
from llmcycle.providers.registry import PROVIDER_REGISTRY
from llmcycle.utils import parse_model, DEFAULT_PRICING, DEFAULT_CONTEXT_WINDOWS
from llmcycle.core.config_loader import ConfigLoader, EnvConfigLoader, RedisConfigLoader
from enum import Enum

class ConfigSource(Enum):
    ENV = "env"
    REDIS = "redis"

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _CacheEntry:
    """In-memory prompt cache entry."""
    __slots__ = ("response", "expires_at")
    def __init__(self, response: CompletionResponse, ttl: float):
        self.response   = response
        self.expires_at = _time.monotonic() + ttl


class LLMCycle:
    """
    All-in-one LLM router and client.

    Quick start::

        client = LLMCycle()
        response = await client.complete("openai/gpt-4o-mini", "What is RAG?")
        async for chunk in client.stream("groq/llama-3.1-70b", "Write a poem"):
            print(chunk, end="")

    With Storage Auto-Save & Unified Drivers::

        from llmcycle.client import LLMCycle, ConfigSource
        from llmcycle.storage import StorageManager
        
        # 1. Setup Storage (Auto-builds Drivers)
        store = StorageManager(url="redis://localhost:6379/0")
        
        # 2. Client auto-inherits the driver for Config Loading!
        client = LLMCycle(
            storage=store, 
            config_source=ConfigSource.REDIS,
            session_id="sess-1", 
            user_id="user-1"
        )

    Dynamic Model Groups (Aliases & Fallbacks)::

        client.router.groups.set("fast", ["groq/llama3", "openai/gpt-4o-mini"])
        
        # ACTIVE_FIRST routing automatically skips exhausted providers!
        # Pass a group as a fallback or primary target:
        response = await client.complete(group="fast", prompt="Hello!", strategy=RoutingStrategy.ACTIVE_FIRST)
        
        # You can also pass both model AND group:
        response = await client.complete(model="openai/gpt-4o", group="fast", prompt="Hello!")

        # Persist groups to your database (SQL/Mongo/Redis)
        await client.router.groups.save()

    Tool calling loop::

        async def execute_tool(name, args):
            if name == "get_weather":
                return {"temp": 18, "city": args["city"]}

        result = await client.complete_with_tools(
            "openai/gpt-4o",
            prompt="What is the weather in London?",
            tools=[{"type": "function", "function": {"name": "get_weather", ...}}],
            tool_executor=execute_tool,
            max_tool_calls=5,
        )

    Structured output::

        class Answer(BaseModel):
            city: str
            temperature: int

        answer = await client.complete_structured(
            "openai/gpt-4o-mini",
            "What is the weather in London? Reply as JSON.",
            schema=Answer,
        )

    Budget enforcement::

        client = LLMCycle(max_cost_usd=1.00)   # raises BudgetExceededError at $1

    Prompt Caching & Semantic Caching::

        # Exact match cache
        res1 = await client.complete("openai/gpt-4o", "What is 2+2?", cache_ttl=300)
        res2 = await client.complete("openai/gpt-4o", "What is 2+2?", cache_ttl=300) # Instant
        
        # Semantic cache (TF-IDF Cosine Similarity)
        client = LLMCycle(semantic_cache=SemanticCache(similarity_threshold=0.85))
        res3 = await client.complete("openai/gpt-4o", "How do I build a RAG app?")
        res4 = await client.complete("openai/gpt-4o", "What's the best way to make a RAG application?") # Instant
    Args:
        env_path: Path to the .env file for auto-loading provider configs.
        fallbacks: Optional dictionary of fallback chains mapping models/providers to a list of fallback models.
        groups: Optional dictionary mapping group names to a list of models. Groups can be dynamically managed via `client.router.groups`.
        strategy: Routing strategy enum. E.g., PRIORITY, ROUND_ROBIN, LOWEST_LATENCY, COST_OPTIMIZED, ACTIVE_FIRST.
        config_source: Source for config auto-loading (ENV or REDIS).
        config_prefix: Prefix for searching config keys.
        config_suffix: Suffix for searching config keys (e.g., _API_KEYS).
        redis_url: Redis URL if config_source=REDIS.
        log_level: Logging level (e.g., "WARNING").
        storage: Optional StorageManager instance. If provided, enables DB persistence for configs, history, groups, etc.
        session_id: Default session stamped on all requests.
        user_id: Default user stamped on all requests.
        team_id: Default team stamped on all requests.
        workplace_id: Default workplace stamped on all requests.
        max_cost_usd: Hard budget enforcement.
        pricing: Custom pricing override dictionary.
        context_windows: Custom context window dictionary.
        auto_trim_context: Automatically truncate messages if over context limit.
        cache: Cache settings for prompts (True for InMemory or instance of BaseCache).
        semantic_cache: Semantic similarity cache for prompt matching.
        rate_limits: Client-side rate limiting dictionary.
        guardrail: True to enable default guardrail, or instance of GuardrailManager.
        injection_guard: True to enable prompt injection guards.
        attachment_storage: Storage path/type for attachments.
        proxy: Proxy string for network requests.
    """

    def __init__(
        self,
        env_path: str = ".env",
        fallbacks: Optional[Dict[str, List[str]]] = None,
        groups: Optional[Dict[str, List[str]]] = None,
        strategy: RoutingStrategy = RoutingStrategy.PRIORITY,
        config_source: ConfigSource = ConfigSource.ENV,
        config_prefix: str = "",
        config_suffix: str = "_API_KEYS",
        redis_url: Optional[str] = None,
        log_level: str = "WARNING",
        # Storage integration
        storage=None,                      # Optional[StorageManager]
        session_id: Optional[str] = None,  # default session stamped on all requests
        user_id: Optional[str] = None,     # default user stamped on all requests
        team_id: Optional[str] = None,
        workplace_id: Optional[str] = None,
        # Budget enforcement
        max_cost_usd: Optional[float] = None,
        # Pricing override
        pricing: Optional[Dict[str, Dict[str, float]]] = None,
        # Context window limits
        context_windows: Optional[Dict[str, int]] = None,
        auto_trim_context: bool = True,    # auto-truncate messages if over context limit
        # Caching layer
        cache: Optional[Union[bool, BaseCache]] = False,  # Pluggable prompt cache
        semantic_cache: Optional[Union[bool, SemanticCache]] = False,  # Semantic similarity cache
        # Rate limits
        rate_limits: Optional[Union[bool, Dict[str, Dict[str, int]]]] = False,
        # Guardrails
        guardrail: Optional[Union[bool, Any]] = False,
        # Prompt injection / jailbreak protection
        injection_guard: Optional[Union[bool, InjectionGuard]] = False,
        # Attachment Storage integration
        attachment_storage: Optional[str] = None,
        attachment_config: Optional[dict] = None,
        # Proxy settings
        proxy: Optional[str] = None,
    ):
        logging.basicConfig(level=getattr(logging, log_level.upper(), logging.WARNING))

        # BOM-aware .env loader
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

        self.key_manager  = KeyManager()
        self._providers: Dict[str, OpenAICompatibleProvider] = {}

        self.storage      = storage
        self.session_id   = session_id
        self.user_id      = user_id
        self.team_id      = team_id
        self.workplace_id = workplace_id

        from llmcycle.core.attachments import AttachmentManager
        att_cfg = attachment_config or {}
        self.attachment_manager = AttachmentManager(
            storage_type=attachment_storage,
            **att_cfg
        )

        self.max_cost_usd    = max_cost_usd
        self._total_cost_usd = 0.0         # accumulated cost this session
        self.proxy           = proxy

        self.pricing         = {**DEFAULT_PRICING, **(pricing or {})}
        self.context_windows = {**DEFAULT_CONTEXT_WINDOWS, **(context_windows or {})}
        self.auto_trim_context = auto_trim_context

        self._aliases: Dict[str, str] = {}

        self._cache = None
        if cache is True:
            self._cache = InMemoryCache()
        elif cache:
            self._cache = cache

        self.rate_limit_manager = None
        if rate_limits is True:
            from llmcycle.core.rate_limit import RateLimitManager
            self.rate_limit_manager = RateLimitManager({"default": {"rpm": 60, "tpm": 40000}})
        elif rate_limits:
            from llmcycle.core.rate_limit import RateLimitManager
            self.rate_limit_manager = RateLimitManager(rate_limits)

        self.guardrail = None
        if guardrail is True:
            from llmcycle.core.guardrail import GuardrailManager
            self.guardrail = GuardrailManager()
        elif guardrail:
            self.guardrail = guardrail

        self.injection_guard: Optional[InjectionGuard] = None
        if injection_guard is True:
            self.injection_guard = InjectionGuard()
        elif injection_guard:
            self.injection_guard = injection_guard

        self._semantic_cache: Optional[SemanticCache] = None
        if semantic_cache is True:
            self._semantic_cache = SemanticCache()
        elif semantic_cache:
            self._semantic_cache = semantic_cache

        self.prompts = PromptRegistry()

        # Set client.on_before / on_after / on_error / on_trace to async callables:
        #   async def hook(model, messages, kwargs): ...  # on_before
        #   async def hook(model, response): ...          # on_after
        #   async def hook(model, exception): ...         # on_error
        #   async def hook(trace: dict): ...              # on_trace  (OTel-compatible)
        self.on_before: Optional[Callable] = None
        self.on_after:  Optional[Callable] = None
        self.on_error:  Optional[Callable] = None
        self.on_trace:  Optional[Callable] = None

        self.groups = GroupManager(groups)
        self.groups.storage = self.storage
        
        # Initialize the appropriate config loader based on user preferences
        if config_source == ConfigSource.ENV:
            self._config_loader = EnvConfigLoader(prefix=config_prefix, suffix=config_suffix)
        elif config_source == ConfigSource.REDIS:
            active_driver = getattr(self.storage, 'driver', None) if self.storage else None
            if not redis_url and not active_driver:
                raise ValueError("redis_url or a StorageManager with a driver must be provided when using ConfigSource.REDIS")
            self._config_loader = RedisConfigLoader(
                redis_url=redis_url or getattr(active_driver, 'url', ""), 
                prefix=config_prefix, 
                suffix=config_suffix, 
                driver=active_driver
            )
        else:
            raise ValueError(f"Unknown config_source: {config_source}")

        self._auto_load_configs()
        self.router      = ModelRouter(
            fallbacks=fallbacks or {}, 
            groups=self.groups, 
            strategy=strategy, 
            pricing=self.pricing,
            key_manager=self.key_manager
        )
        self._stream_mgr = StreamResilienceManager(self.router, self.key_manager, self._providers)

    # ─── Auto-discovery ──────────────────────────────────────────────────────

    def _auto_load_configs(self):
        """Scan configured loaders and register providers."""
        configs = self._config_loader.load_configs()
        for provider_name, config in configs.items():
                p_key = provider_name.lower()
                keys = [k.strip() for k in config.get("api_keys", "").split(",") if k.strip()]
                if not keys:
                    continue
                base_url = (
                    config.get("base_url")
                    or PROVIDER_REGISTRY.get(provider_name.upper())
                    or f"https://api.{p_key}.com/v1"
                )
                if p_key not in self._providers:
                    self._providers[p_key] = OpenAICompatibleProvider(base_url, provider_name=p_key, proxy=self.proxy)
                self.key_manager.add_keys(p_key, keys)
                logger.info(f"Registered provider [{p_key}] with {len(keys)} key(s) → {base_url}")

    # ─── Provider management ─────────────────────────────────────────────────

    def add_provider(self, name: str, api_keys: List[str], base_url: Optional[str] = None):
        """Manually register a provider at runtime."""
        p = name.lower()
        url = base_url or PROVIDER_REGISTRY.get(name.upper()) or f"https://api.{p}.com/v1"
        self._providers[p] = OpenAICompatibleProvider(url, provider_name=p, proxy=self.proxy)
        self.key_manager.add_keys(p, api_keys)

    def get_providers(self) -> List[str]:
        return list(self._providers.keys())

    async def get_models(self, provider: str) -> List[str]:
        p = provider.lower()
        if p not in self._providers:
            return []
        key = self.key_manager.get_next_key(p)
        if not key:
            return []
        return await self._providers[p].get_models(key)

    async def get_all_live_models(self) -> Dict[str, List[str]]:
        """Fetch all dynamic live models across all configured providers in parallel."""
        providers = self.get_providers()
        tasks = {p: self.get_models(p) for p in providers}
        results = {}
        for p, fut in zip(tasks.keys(), await asyncio.gather(*tasks.values(), return_exceptions=True)):
            if isinstance(fut, Exception):
                logger.warning(f"Failed to fetch live models for {p}: {fut}")
                results[p] = []
            else:
                results[p] = fut
        return results

    def get_key_stats(self, provider: str) -> List[dict]:
        return self.key_manager.get_stats(provider)

    # ─── Aliases ─────────────────────────────────────────────────────────────

    def alias(self, name: str, model: str) -> None:
        """
        Create a model alias.

        Usage::

            client.alias("fast",    "groq/llama-3.1-70b")
            client.alias("smart",   "openai/gpt-4o")
            client.alias("cheap",   "deepseek/deepseek-chat")

            response = await client.complete("fast", "Explain RAG")
            # resolves to groq/llama-3.1-70b automatically
        """
        self._aliases[name] = model

    def _resolve_model(self, model: str) -> str:
        """Resolve alias → real model string."""
        return self._aliases.get(model, model)

    # ─── Pricing helpers ─────────────────────────────────────────────────────

    def _get_pricing(self, model: str) -> Optional[Dict[str, float]]:
        """Return {input, output} pricing for a model (partial match)."""
        model_lower = model.lower()
        for key, price in self.pricing.items():
            if key in model_lower:
                return price
        return None

    def _estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
        price = self._get_pricing(model)
        if not price:
            return None
        return (prompt_tokens / 1000) * price["input"] + (completion_tokens / 1000) * price["output"]

    def get_cost_summary(self) -> Dict[str, float]:
        """Return total accumulated cost for this client session."""
        return {"total_cost_usd": self._total_cost_usd, "budget_usd": self.max_cost_usd}

    def _check_budget(self, new_cost: Optional[float]) -> None:
        """Raise BudgetExceededError if adding new_cost would exceed max_cost_usd."""
        if self.max_cost_usd is not None and new_cost is not None:
            if self._total_cost_usd + new_cost > self.max_cost_usd:
                raise BudgetExceededError(
                    spent=self._total_cost_usd,
                    budget=self.max_cost_usd,
                )

    # ─── Context window helpers ───────────────────────────────────────────────

    def _get_content_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        parts.append(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        parts.append("[Image Attachment]")
                    elif part.get("type") == "input_audio":
                        parts.append("[Audio Attachment]")
                    elif part.get("type") == "document":
                        parts.append("[Document Attachment]")
            return "".join(parts)
        return ""

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return max(1, len(text) // 4)

    def _trim_messages(self, messages: List[dict], model: str, reserve: int = 512) -> List[dict]:
        """
        Auto-trim messages to fit within the model's context window.
        Keeps system message + most recent messages. Removes oldest turns first.
        """
        limit = self.context_windows.get(parse_model(model)[1], 0)
        if not limit:
            return messages

        total = sum(self._estimate_tokens(self._get_content_text(m.get("content", ""))) for m in messages)
        if total + reserve <= limit:
            return messages

        result = []
        # Always keep system messages
        system = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # Add non-system from the end (most recent first)
        budget = limit - reserve - sum(self._estimate_tokens(self._get_content_text(m.get("content", ""))) for m in system)
        kept = []
        for m in reversed(non_system):
            t = self._estimate_tokens(self._get_content_text(m.get("content", "")))
            if budget - t >= 0:
                kept.insert(0, m)
                budget -= t
            else:
                break

        result = system + kept
        logger.warning(f"Auto-trimmed messages from {len(messages)} to {len(result)} to fit context window.")
        return result

    # ─── Prompt cache ─────────────────────────────────────────────────────────

    def _cache_key(self, model: str, messages: List[dict], kwargs: dict) -> str:
        payload = json.dumps({"model": model, "messages": messages, **{
            k: v for k, v in kwargs.items() if k in ("temperature", "max_tokens", "top_p")
        }}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    async def _cache_get(self, key: str) -> Optional[CompletionResponse]:
        if not self._cache:
            return None
        return await self._cache.get(key)

    async def _cache_set(self, key: str, response: CompletionResponse, ttl: float) -> None:
        if not self._cache:
            return
        await self._cache.set(key, response, ttl)

    async def cache_clear(self) -> int:
        """Clear all cached responses. Returns number of entries cleared."""
        if not self._cache:
            return 0
        return await self._cache.clear()

    async def cache_stats(self) -> Dict[str, Any]:
        """Return info about current prompt cache state."""
        if not self._cache:
            return {}
        return await self._cache.stats()

    # ─── Storage helpers ──────────────────────────────────────────────────────

    async def _save(self, **kwargs) -> None:
        """Fire-and-forget storage save (non-fatal)."""
        if not self.storage:
            return
        try:
            from llmcycle.storage.models import LLMRequest as _R
            await self.storage.save_request(_R(**kwargs))
        except Exception as e:
            logger.warning(f"Storage save failed (non-fatal): {e}")

    # ─── Inference: complete ──────────────────────────────────────────────────

    async def complete(
        self,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
        messages: Optional[List[dict]] = None,
        group: Optional[str] = None,
        strategy: Optional[RoutingStrategy] = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        cache_ttl: Optional[float] = None,    # seconds; None = no cache
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
        workplace_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        parent_request_id: Optional[str] = None,
        turn_number: int = 0,
        attachments: Optional[List[Union[str, bytes, dict]]] = None,
        shadow_models: Optional[List[str]] = None,
        validators: Optional[List[Callable]] = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        One-shot completion with smart retry.

        Args:
            model:              Model string, e.g. "openai/gpt-4o-mini" or an alias.
            prompt:             User prompt (convenience — builds a single user message).
            messages:           Full messages list (overrides prompt).
            group:              Optional group ID to use for routing/fallback. 
                                If both model and group are provided, model is tried first, 
                                and group is used as the fallback list.
            strategy:           Optional RoutingStrategy override for this request.
            cache_ttl:          Cache identical prompts for this many seconds (0 = no cache).
            parent_request_id:  Link to a parent request (used in tool-call chains).
            turn_number:        Which turn in an agentic loop (0 = first user turn).
            timeout:            Raise asyncio.TimeoutError after N seconds.
            tags:               Labels saved with the storage record.
            attachments:        Optional list of documents, audio, video, or image attachments.
            shadow_models:      Fire-and-forget completions on these models in parallel
                                (dark launching / A/B). Results are logged only.
            validators:         List of callables (sync or async) — each receives
                                (model, response) and raises on failure. On validator
                                failure the call behaves as an error (no retry via
                                shadow_models but surfaces the ValidationError).
        """
        if not model and not group:
            raise ValueError("Must provide 'model' or 'group'.")
            
        if model:
            model = self._resolve_model(model)

        if messages is None:
            if prompt is None:
                raise ValueError("Provide either 'prompt' or 'messages'.")
            if attachments:
                messages = [{"role": "user", "content": self.attachment_manager.format_message_content(prompt, attachments)}]
            else:
                messages = [{"role": "user", "content": prompt}]
        elif attachments:
            # Attach to the last user message in the message list
            # Find the last message with role "user"
            messages = [dict(m) for m in messages]  # Make a copy to avoid side-effects
            user_msg_idx = None
            for idx in range(len(messages) - 1, -1, -1):
                if messages[idx].get("role") == "user":
                    user_msg_idx = idx
                    break
            if user_msg_idx is not None:
                current_content = messages[user_msg_idx].get("content", "")
                messages[user_msg_idx]["content"] = self.attachment_manager.format_message_content(
                    self._get_content_text(current_content),
                    attachments
                )
            else:
                messages.append({"role": "user", "content": self.attachment_manager.format_message_content("", attachments)})

        if self.injection_guard:
            prompt_text_for_guard = prompt or "".join(
                self._get_content_text(m.get("content", ""))
                for m in (messages or [])
                if m.get("role") == "user"
            )
            result = self.injection_guard.scan(prompt_text_for_guard)
            if result.blocked:
                raise InjectionBlockedError(result)

        if self._semantic_cache and (prompt or messages):
            _sc_query = prompt or " ".join(
                self._get_content_text(m.get("content", "")) for m in messages
            )
            _sc_hit = await self._semantic_cache.get(_sc_query)
            if _sc_hit:
                logger.debug(f"Semantic cache hit for model={model}")
                return _sc_hit

        # Rate Limit check
        if self.rate_limit_manager:
            prompt_text = prompt or "".join(self._get_content_text(m.get("content", "")) for m in messages)
            est_tokens = self._estimate_tokens(prompt_text)
            await self.rate_limit_manager.get_limiter(model or group).acquire(est_tokens)

        # Guardrails: Mask prompt/messages in-flight
        if self.guardrail:
            if messages:
                new_messages = []
                for m in messages:
                    c = m.get("content")
                    if isinstance(c, str):
                        new_messages.append({**m, "content": self.guardrail.mask_prompt(c)})
                    elif isinstance(c, list):
                        new_parts = []
                        for part in c:
                            if isinstance(part, dict) and part.get("type") == "text":
                                new_parts.append({**part, "text": self.guardrail.mask_prompt(part.get("text", ""))})
                            else:
                                new_parts.append(part)
                        new_messages.append({**m, "content": new_parts})
                    else:
                        new_messages.append(m)
                messages = new_messages
            if prompt:
                prompt = self.guardrail.mask_prompt(prompt)

        # Context trim
        if self.auto_trim_context:
            messages = self._trim_messages(messages, model or group or "")

        # Prompt cache check
        cache_key = None
        if cache_ttl:
            cache_key = self._cache_key(model or group or "", messages, kwargs)
            cached = await self._cache_get(cache_key)
            if cached:
                logger.debug(f"Prompt cache hit for model={model}")
                await self._save(
                    model=model or group or "", provider=cached.provider or "",
                    prompt=prompt or "", response=cached.content or "",
                    prompt_tokens=cached.prompt_tokens or 0,
                    completion_tokens=cached.completion_tokens or 0,
                    status="success", is_cached=True,
                    session_id=session_id or self.session_id,
                    user_id=user_id or self.user_id,
                    team_id=team_id or self.team_id,
                    workplace_id=workplace_id or self.workplace_id,
                    tags=tags or [], parent_request_id=parent_request_id,
                    turn_number=turn_number,
                )
                return cached

        # Before hook
        if self.on_before:
            try:
                await self.on_before(model or group or "", messages, kwargs)
            except Exception as e:
                logger.warning(f"on_before hook raised: {e}")

        req = CompletionRequest(
            model=model or group,
            messages=[Message(**m) for m in messages],
            **kwargs,
        )
        policy = RetryPolicy(max_retries=max_retries, retry_delay=retry_delay)
        t0 = _time.monotonic()
        error_msg: Optional[str] = None
        status = "success"
        cancelled_at: Optional[float] = None
        response = None

        try:
            coro = self._stream_mgr.complete(req, retry_policy=policy, strategy=strategy, group=group)
            response = await (asyncio.wait_for(coro, timeout=timeout) if timeout else coro)

            # Unmask response if guardrails are active
            if response and response.content and self.guardrail:
                response.content = self.guardrail.unmask_response(response.content)

            if validators and response:
                for validator in validators:
                    try:
                        result = validator(model or group or "", response)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as ve:
                        logger.warning(f"Response validator {validator.__name__!r} failed: {ve}")
                        raise

            if shadow_models and response:
                async def _shadow_call(shadow_model: str, _msgs: list, _kw: dict):
                    try:
                        shadow_resp = await self.complete(
                            shadow_model, messages=_msgs, **_kw
                        )
                        logger.info(
                            f"[Shadow] model={shadow_model} "
                            f"tokens={shadow_resp.prompt_tokens}+{shadow_resp.completion_tokens} "
                            f"latency={shadow_resp.latency_ms:.0f}ms"
                        )
                    except Exception as se:
                        logger.warning(f"[Shadow] model={shadow_model} failed: {se}")

                _shadow_kw = {k: v for k, v in kwargs.items()}
                for _sm in shadow_models:
                    asyncio.ensure_future(
                        _shadow_call(self._resolve_model(_sm), list(messages), _shadow_kw)
                    )

            # After hook
            if self.on_after:
                try:
                    await self.on_after(model or group or "", response)
                except Exception as e:
                    logger.warning(f"on_after hook raised: {e}")

        except asyncio.CancelledError:
            status = "cancelled"; cancelled_at = _time.time(); error_msg = "Request cancelled"
            raise
        except asyncio.TimeoutError:
            status = "timeout"; error_msg = f"Exceeded {timeout}s timeout"
            raise
        except Exception as e:
            error_msg = str(e); status = "error"
            if self.on_error:
                try:
                    await self.on_error(model or group or "", e)
                except Exception:
                    pass
            raise
        finally:
            latency_ms = round((_time.monotonic() - t0) * 1000, 2)
            cost = self._estimate_cost(
                model or group or "",
                getattr(response, "prompt_tokens", 0) or 0,
                getattr(response, "completion_tokens", 0) or 0,
            )
            self._check_budget(cost)
            if cost:
                self._total_cost_usd += cost
            price = self._get_pricing(model or group or "")
            await self._save(
                model=model or group or "",
                provider=getattr(response, "provider", ""),
                prompt=prompt or "",
                response=getattr(response, "content", ""),
                prompt_tokens=getattr(response, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(response, "completion_tokens", 0) or 0,
                latency_ms=latency_ms,
                timeout_ms=timeout * 1000 if timeout else None,
                status=status, error=error_msg, cancelled_at=cancelled_at,
                cost_usd=cost,
                input_cost_per_1k=price["input"] if price else None,
                output_cost_per_1k=price["output"] if price else None,
                session_id=session_id or self.session_id,
                user_id=user_id or self.user_id,
                team_id=team_id or self.team_id,
                workplace_id=workplace_id or self.workplace_id,
                tags=tags or [],
                parent_request_id=parent_request_id,
                turn_number=turn_number,
            )

        # Cache the response
        if cache_key and response:
            await self._cache_set(cache_key, response, cache_ttl)

        # Semantic cache: store on success
        if self._semantic_cache and response and status == "success":
            _sc_store_query = prompt or " ".join(
                self._get_content_text(m.get("content", "")) for m in messages
            )
            await self._semantic_cache.set(_sc_store_query, response)

        if self.on_trace and response:
            try:
                trace_span = {
                    "name":               "llmcycle.complete",
                    "model":              model or group or "",
                    "provider":           getattr(response, "provider", ""),
                    "status":             status,
                    "latency_ms":         round((_time.monotonic() - t0) * 1000, 2),
                    "prompt_tokens":      getattr(response, "prompt_tokens", 0),
                    "completion_tokens":  getattr(response, "completion_tokens", 0),
                    "cost_usd":           self._estimate_cost(
                        model or group or "",
                        getattr(response, "prompt_tokens", 0),
                        getattr(response, "completion_tokens", 0),
                    ),
                    "session_id":         session_id or self.session_id,
                    "user_id":            user_id or self.user_id,
                    "tags":               tags or [],
                    "timestamp":          _time.time(),
                }
                _t = self.on_trace(trace_span)
                if asyncio.iscoroutine(_t):
                    await _t
            except Exception as te:
                logger.warning(f"on_trace hook raised: {te}")

        return response

    # ─── Inference: stream ────────────────────────────────────────────────────

    async def stream(
        self,
        model: Optional[str] = None,
        prompt: Optional[str] = None,
        messages: Optional[List[dict]] = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        group: Optional[str] = None,
        strategy: Optional[RoutingStrategy] = None,
        stop_event: Optional[asyncio.Event] = None,
        timeout: Optional[float] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
        workplace_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        parent_request_id: Optional[str] = None,
        turn_number: int = 0,
        attachments: Optional[List[Union[str, bytes, dict]]] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Stream output from the LLM, auto-recovering on failure.

        Args:
            model:       Model to use.
            prompt:      The user prompt.
            messages:    Alternatively, full message list.
            group:       Optional group ID for routing.
            strategy:    Optional RoutingStrategy override.
        """
        if not model and not group:
            raise ValueError("Must provide 'model' or 'group'.")
            
        if model:
            model = self._resolve_model(model)

        if messages is None:
            if prompt is None:
                raise ValueError("Provide either 'prompt' or 'messages'.")
            if attachments:
                messages = [{"role": "user", "content": self.attachment_manager.format_message_content(prompt, attachments)}]
            else:
                messages = [{"role": "user", "content": prompt}]
        elif attachments:
            # Attach to the last user message in the message list
            # Find the last message with role "user"
            messages = [dict(m) for m in messages]  # Make a copy to avoid side-effects
            user_msg_idx = None
            for idx in range(len(messages) - 1, -1, -1):
                if messages[idx].get("role") == "user":
                    user_msg_idx = idx
                    break
            if user_msg_idx is not None:
                current_content = messages[user_msg_idx].get("content", "")
                messages[user_msg_idx]["content"] = self.attachment_manager.format_message_content(
                    self._get_content_text(current_content),
                    attachments
                )
            else:
                messages.append({"role": "user", "content": self.attachment_manager.format_message_content("", attachments)})

        # Rate Limit check
        if self.rate_limit_manager:
            prompt_text = prompt or "".join(self._get_content_text(m.get("content", "")) for m in messages)
            est_tokens = self._estimate_tokens(prompt_text)
            await self.rate_limit_manager.get_limiter(model or group).acquire(est_tokens)

        # Guardrails: Mask prompt/messages in-flight
        if self.guardrail:
            if messages:
                new_messages = []
                for m in messages:
                    c = m.get("content")
                    if isinstance(c, str):
                        new_messages.append({**m, "content": self.guardrail.mask_prompt(c)})
                    elif isinstance(c, list):
                        new_parts = []
                        for part in c:
                            if isinstance(part, dict) and part.get("type") == "text":
                                new_parts.append({**part, "text": self.guardrail.mask_prompt(part.get("text", ""))})
                            else:
                                new_parts.append(part)
                        new_messages.append({**m, "content": new_parts})
                    else:
                        new_messages.append(m)
                messages = new_messages
            if prompt:
                prompt = self.guardrail.mask_prompt(prompt)

        if self.auto_trim_context:
            messages = self._trim_messages(messages, model or group or "")

        req = CompletionRequest(
            model=model or group,
            messages=[Message(**m) for m in messages],
            stream=True,
            **kwargs,
        )
        policy = RetryPolicy(max_retries=max_retries, retry_delay=retry_delay)
        t0 = _time.monotonic()
        deadline = (t0 + timeout) if timeout else None
        chunks: List[str] = []
        error_msg: Optional[str] = None
        status = "success"
        cancelled_at: Optional[float] = None
        first_chunk_at: Optional[float] = None

        try:
            async for chunk in self._stream_mgr.safe_stream(req, stop_event=stop_event, retry_policy=policy, strategy=strategy, group=group):
                if deadline and _time.monotonic() > deadline:
                    status = "timeout"; error_msg = f"Stream exceeded {timeout}s"; cancelled_at = _time.time()
                    break
                if stop_event and stop_event.is_set():
                    status = "cancelled"; cancelled_at = _time.time(); error_msg = "Stream cancelled by caller"
                    if self.guardrail:
                        chunk = self.guardrail.unmask_response(chunk)
                    chunks.append(chunk); yield chunk
                    break
                if first_chunk_at is None:
                    first_chunk_at = _time.monotonic()
                if self.guardrail:
                    chunk = self.guardrail.unmask_response(chunk)
                chunks.append(chunk)
                yield chunk
        except asyncio.CancelledError:
            status = "cancelled"; cancelled_at = _time.time(); error_msg = "Stream task cancelled"
            raise
        except Exception as e:
            error_msg = str(e); status = "error"
            raise
        finally:
            latency_ms = round((_time.monotonic() - t0) * 1000, 2)
            ttft = round((first_chunk_at - t0) * 1000, 2) if first_chunk_at else None
            price = self._get_pricing(model or group or "")
            
            response_text = "".join(chunks)
            if self.guardrail:
                response_text = self.guardrail.unmask_response(response_text)
                
            await self._save(
                model=model or group or "", provider="",
                prompt=prompt or "", response=response_text,
                latency_ms=latency_ms, time_to_first_token_ms=ttft,
                timeout_ms=timeout * 1000 if timeout else None,
                status=status, error=error_msg, cancelled_at=cancelled_at,
                session_id=session_id or self.session_id,
                user_id=user_id or self.user_id,
                team_id=team_id or self.team_id,
                workplace_id=workplace_id or self.workplace_id,
                tags=tags or [],
                parent_request_id=parent_request_id,
                turn_number=turn_number,
            )

    # ─── Structured output ────────────────────────────────────────────────────

    async def complete_structured(
        self,
        model: str,
        prompt: Optional[str] = None,
        messages: Optional[List[dict]] = None,
        schema: Type[T] = None,
        group: Optional[str] = None,
        strategy: Optional[RoutingStrategy] = None,
        max_retries_parse: int = 2,
        use_tool_format: bool = True,   # ← True by default: tool-calling is more reliable
        **kwargs,
    ) -> T:
        """
        Complete and return a strictly validated Pydantic object.

        Args:
            model:    Model to use.
            prompt:   The prompt text.
            messages: Alternatively, full message list.
            schema:   Pydantic model class to validate output against.
            group:    Optional group ID for routing.
            strategy: Optional RoutingStrategy override.
        """
        if schema is None:
            raise ValueError("schema= is required for complete_structured()")

        # ── Build base messages ──────────────────────────────────────────────
        if messages is None:
            if prompt is None:
                raise ValueError("Provide either 'prompt' or 'messages'.")
            base_messages = [{"role": "user", "content": prompt}]
        else:
            base_messages = list(messages)

        # ════════════════════════════════════════════════════════════════════
        # MODE A — Tool-calling (default, most reliable)
        # The schema is converted into an OpenAI function definition.
        # The model MUST call it, so fields arrive pre-parsed — zero JSON
        # parsing headaches, zero markdown stripping.
        # ════════════════════════════════════════════════════════════════════
        if use_tool_format:
            tool_name = f"extract_{schema.__name__.lower()}"
            tool_def = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": (
                        f"Extract and return structured data as a {schema.__name__} object. "
                        "Fill every field accurately based on the conversation."
                    ),
                    "parameters": schema.model_json_schema(),
                },
            }

            response = await self.complete(
                model,
                group=group,
                strategy=strategy,
                messages=base_messages,
                tools=[tool_def],
                tool_choice={"type": "function", "function": {"name": tool_name}},
                **kwargs,
            )

            # Parse the tool-call arguments if the model returned one
            raw_tool_calls = getattr(response, "tool_calls", None) or []
            for tc in raw_tool_calls:
                fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
                if fn.get("name") == tool_name:
                    args_raw = fn.get("arguments", "{}")
                    try:
                        data = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                        return schema.model_validate(data)
                    except Exception as e:
                        logger.warning(
                            f"complete_structured tool-call parse failed ({e}); "
                            "falling back to JSON-prompt mode."
                        )
                        break  # fall through to MODE B below

            # No tool_calls in response — provider doesn't support it; fall back
            logger.info(
                "complete_structured: no tool_calls in response — "
                "retrying with JSON-prompt fallback."
            )

        # ════════════════════════════════════════════════════════════════════
        # MODE B — JSON-prompt (legacy / explicit fallback)
        # The model is asked to output plain JSON. We parse it ourselves,
        # with self-correction loops on failure.
        # ════════════════════════════════════════════════════════════════════
        schema_hint = (
            f"Reply ONLY with valid JSON matching this schema: "
            f"{json.dumps(schema.model_json_schema(), indent=2)}\n"
            "Do not include any text outside the JSON object."
        )
        fb_messages = [{"role": "system", "content": schema_hint}] + base_messages

        last_error = None
        raw = ""
        for attempt in range(max_retries_parse + 1):
            response = await self.complete(model, group=group, strategy=strategy, messages=fb_messages, **kwargs)
            raw = (response.content or "").strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            try:
                data = json.loads(raw)
                return schema.model_validate(data)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"complete_structured JSON-prompt attempt {attempt+1} failed: {e}"
                )
                if attempt < max_retries_parse:
                    # Self-correction: feed the bad output + error back to the model
                    fb_messages = list(fb_messages) + [
                        {"role": "assistant", "content": raw},
                        {
                            "role": "user",
                            "content": (
                                f"The response was not valid JSON or did not match the schema.\n"
                                f"Validation error: {e}\n"
                                "Please output ONLY a valid JSON object that matches the schema."
                            ),
                        },
                    ]

        raise StructuredOutputError(
            f"Failed to parse LLM response into {schema.__name__} after "
            f"{max_retries_parse+1} attempts: {last_error}",
            raw_response=raw,
        )

    # ─── Agentic tool loop ────────────────────────────────────────────────────

    async def complete_with_tools(
        self,
        model: str,
        prompt: Optional[str] = None,
        messages: Optional[List[dict]] = None,
        tools: Optional[List[dict]] = None,
        tool_executor: Optional[Callable] = None,
        max_tool_calls: int = 10,
        group: Optional[str] = None,
        strategy: Optional[RoutingStrategy] = None,
        timeout: Optional[float] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        **kwargs,
    ) -> CompletionResponse:
        """
        Run a full agentic tool-calling loop.

        Automatically:
          1. Calls the LLM with your tools list
          2. Detects tool_calls in the response
          3. Executes each tool via tool_executor(name, arguments) -> result
          4. Appends tool results to messages and loops
          5. Stops when the model returns a final text response (no tool calls)
          6. Raises MaxToolCallsExceededError if max_tool_calls is exceeded
          7. Saves every intermediate request + tool call to storage

        Args:
            model:          "provider/model-name"
            prompt:         User prompt (or pass messages=)
            messages:       Full messages list (overrides prompt)
            tools:          OpenAI-format tool definitions list
            tool_executor:  async or sync callable: (name: str, arguments: dict) -> Any
                            Return value is JSON-serialized and sent back to the LLM
            max_tool_calls: Hard cap on total tool calls (default: 10)
            timeout:        Per-turn timeout in seconds

        Usage::

            async def my_tools(name, args):
                if name == "get_weather":
                    return {"temp": 18, "city": args["city"]}
                if name == "search":
                    return {"results": ["doc1", "doc2"]}

            final = await client.complete_with_tools(
                "openai/gpt-4o",
                prompt="What is the weather in London and Paris?",
                tools=[get_weather_schema, search_schema],
                tool_executor=my_tools,
                max_tool_calls=6,
            )
            print(final.content)
        """
        model = self._resolve_model(model)

        if messages is None:
            if prompt is None:
                raise ValueError("Provide either 'prompt' or 'messages'.")
            messages = [{"role": "user", "content": prompt}]

        messages = list(messages)  # local copy
        tool_call_count = 0
        parent_req_id: Optional[str] = None

        while True:
            response = await self.complete(
                model,
                messages=messages,
                tools=tools or [],
                timeout=timeout,
                session_id=session_id or self.session_id,
                user_id=user_id or self.user_id,
                tags=tags,
                parent_request_id=parent_req_id,
                turn_number=tool_call_count,
                **kwargs,
            )

            # Track parent chain
            if hasattr(response, "request_id"):
                parent_req_id = response.request_id

            # Check if the model wants to call tools
            raw_tool_calls = getattr(response, "tool_calls", None) or []

            if not raw_tool_calls:
                # No tool calls — this is the final response
                return response

            # Append the assistant turn with tool calls to messages
            messages.append({
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": raw_tool_calls,
            })

            # Execute each tool call
            for tc in raw_tool_calls:
                if tool_call_count >= max_tool_calls:
                    raise MaxToolCallsExceededError(
                        tool_call_count=tool_call_count,
                        max_tool_calls=max_tool_calls,
                        partial_messages=messages,
                    )

                tc_id   = tc.get("id", "")
                tc_name = tc.get("function", {}).get("name", "")
                tc_args_raw = tc.get("function", {}).get("arguments", "{}")

                try:
                    tc_args = json.loads(tc_args_raw) if isinstance(tc_args_raw, str) else tc_args_raw
                except json.JSONDecodeError:
                    tc_args = {}

                # Execute
                if tool_executor:
                    if asyncio.iscoroutinefunction(tool_executor):
                        result = await tool_executor(tc_name, tc_args)
                    else:
                        result = tool_executor(tc_name, tc_args)
                else:
                    result = {"error": f"No tool_executor registered for '{tc_name}'"}

                result_str = json.dumps(result) if not isinstance(result, str) else result

                # Save tool call to storage
                if self.storage:
                    try:
                        from llmcycle.storage.models import ToolCall as _TC
                        _tc_obj = _TC(
                            request_id=parent_req_id or "",
                            session_id=session_id or self.session_id,
                            user_id=user_id or self.user_id,
                            name=tc_name,
                            arguments=tc_args,
                            arguments_raw=tc_args_raw if isinstance(tc_args_raw, str) else json.dumps(tc_args_raw),
                            result=result_str,
                            executed_at=_time.time(),
                            status="success",
                        )
                        await self.storage.save_tool_call(_tc_obj)
                    except Exception as e:
                        logger.warning(f"Tool call storage save failed: {e}")

                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_str,
                })
                tool_call_count += 1

    # ─── Batch completions ────────────────────────────────────────────────────

    async def complete_batch(
        self,
        model: str,
        prompts: List[str],
        max_retries: int = 2,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        cache_ttl: Optional[float] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        concurrency: int = 5,
        **kwargs,
    ) -> List[Optional[CompletionResponse]]:
        """
        Run multiple prompts in parallel against the same model.

        Returns a list in the same order as prompts. Failed items return None.

        Usage::

            responses = await client.complete_batch(
                "openai/gpt-4o-mini",
                ["Explain RAG", "Explain LoRA", "Explain RLHF"],
                concurrency=3,
            )
        """
        sem = asyncio.Semaphore(concurrency)

        async def _one(p: str) -> Optional[CompletionResponse]:
            async with sem:
                try:
                    return await self.complete(
                        model, prompt=p,
                        max_retries=max_retries, retry_delay=retry_delay,
                        timeout=timeout, cache_ttl=cache_ttl,
                        session_id=session_id, user_id=user_id, tags=tags,
                        **kwargs,
                    )
                except Exception as e:
                    logger.warning(f"Batch item failed: {e}")
                    return None

        return list(await asyncio.gather(*[_one(p) for p in prompts]))

    # ─── Context manager support ─────────────────────────────────────────────

    async def __aenter__(self):
        if self.storage:
            await self.storage.connect()
        return self

    async def __aexit__(self, *_):
        if self.storage:
            await self.storage.disconnect()

    def __repr__(self) -> str:
        return (
            f"LLMCycle(providers={self.get_providers()}, "
            f"strategy={self.router.strategy.value}, "
            f"storage={'yes' if self.storage else 'no'}, "
            f"cost=${self._total_cost_usd:.4f})"
        )
