"""
StreamResilienceManager - Smart LLM Manager
============================================
Smart retry logic:
  1. User sets max_retries (default 2) and retry_delay (default 1.0s)
  2. Before each retry, check if more keys exist for the same provider
     - Yes → rotate key and retry immediately (no delay)
     - No  → wait retry_delay, then fall over to next provider
  3. Across all providers: respect sort order from router

Scenarios handled:
  SCENARIO 1 – Provider drops connection mid-stream
    → Capture partial text, inject context, failover

  SCENARIO 2 – Rate-limit / Auth error during stream
    → Rotate key if available, else failover with retry_delay wait

  SCENARIO 3 – Consumer stops (GeneratorExit / stop_event / CancelledError)
    → Clean exit, HTTP connection released

  SCENARIO 4 – Content policy
    → Fail immediately, no retry ever

Smart retry decision tree:
  On ANY retriable error:
    if provider has another usable key:
       → rotate key, retry NOW (counts toward max_retries)
    elif retries_remaining > 0:
       → wait retry_delay seconds, try next provider
    else:
       → move to next provider in fallback chain immediately
"""
from __future__ import annotations
import asyncio
import logging
import time
from typing import AsyncGenerator, List, Optional

from llmcycle.schema import CompletionRequest, CompletionResponse, Message
from llmcycle.core.errors import (
    LLMCycleError, RateLimitError, AuthenticationError,
    QuotaExceededError, ContentPolicyError,
    AllProvidersFailedError,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_DELAY = 1.0  # seconds


class RetryPolicy:
    """Encapsulates retry + delay configuration."""
    def __init__(self, max_retries: int = DEFAULT_MAX_RETRIES, retry_delay: float = DEFAULT_RETRY_DELAY):
        self.max_retries = max_retries
        self.retry_delay = retry_delay


class SmartRetryState:
    """Tracks retry budget per request."""
    def __init__(self, policy: RetryPolicy):
        self.policy = policy
        self.retries_used = 0

    @property
    def has_budget(self) -> bool:
        return self.retries_used < self.policy.max_retries

    def consume(self):
        self.retries_used += 1

    async def wait_if_needed(self, provider_name: str, has_alt_key: bool):
        """
        Smart wait logic:
          - If another key is available for same provider → no wait, rotate immediately
          - Else if retry budget remains → wait retry_delay, try next provider
        """
        if has_alt_key:
            logger.info(f"[{provider_name}] Alternative key available — rotating immediately (no delay)")
            return
        if self.has_budget:
            logger.info(
                f"[{provider_name}] No alternative keys. "
                f"Waiting {self.policy.retry_delay}s before next provider "
                f"(retry {self.retries_used + 1}/{self.policy.max_retries})"
            )
            await asyncio.sleep(self.policy.retry_delay)
            self.consume()


class StreamResilienceManager:
    """Smart LLM Manager with adaptive retry, key rotation, and stream failover."""

    def __init__(self, router, key_manager, providers: dict):
        self.router = router
        self.key_manager = key_manager
        self.providers = providers

    def _default_policy(self) -> RetryPolicy:
        return RetryPolicy(DEFAULT_MAX_RETRIES, DEFAULT_RETRY_DELAY)

    def _has_alt_key(self, provider: str) -> bool:
        """Returns True if the provider has at least one MORE usable key right now."""
        stats = self.key_manager.key_count(provider)
        return stats["active"] > 0

    # ─── Non-streaming ───────────────────────────────────────────────────

    async def complete(
        self,
        request: CompletionRequest,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> CompletionResponse:
        """
        Smart completion with adaptive retry.
        - Rotates keys within a provider before falling back.
        - Waits retry_delay only when no more keys exist for current provider.
        """
        policy = retry_policy or self._default_policy()
        state = SmartRetryState(policy)
        route = self.router.get_route(request.model)
        errors: List[LLMCycleError] = []

        for provider_name, model in route:
            if provider_name not in self.providers:
                continue

            provider = self.providers[provider_name]
            # Attempt keys for this provider until none left or max tries
            keys_tried = 0
            max_keys_to_try = max(policy.max_retries + 1, self.key_manager.key_count(provider_name)["total"])

            while keys_tried < max_keys_to_try:
                key = self.key_manager.get_next_key(provider_name)
                if not key:
                    break
                keys_tried += 1

                req = request.model_copy(deep=True)
                req.model = model or request.model

                try:
                    t0 = time.monotonic()
                    response = await provider.generate(req, key)
                    latency = (time.monotonic() - t0) * 1000
                    self.router.record_latency(provider_name, latency)
                    self.key_manager.report_success(provider_name, key)
                    logger.info(f"[{provider_name}] Success in {latency:.0f}ms")
                    return response

                except ContentPolicyError:
                    raise  # Never retry

                except AuthenticationError as e:
                    self.key_manager.report_error(provider_name, key, "auth")
                    errors.append(e)
                    # Try next key immediately (it's disabled, rotation will skip it)
                    continue

                except (RateLimitError, QuotaExceededError) as e:
                    err_type = "rate_limit" if isinstance(e, RateLimitError) else "quota"
                    self.key_manager.report_error(provider_name, key, err_type)
                    errors.append(e)
                    has_alt = self._has_alt_key(provider_name)
                    await state.wait_if_needed(provider_name, has_alt)
                    if has_alt:
                        continue  # rotate key
                    break  # no more keys → next provider

                except LLMCycleError as e:
                    self.key_manager.report_error(provider_name, key, "server")
                    errors.append(e)
                    has_alt = self._has_alt_key(provider_name)
                    await state.wait_if_needed(provider_name, has_alt)
                    if has_alt:
                        continue
                    break

            # Check if retry budget exhausted
            if not state.has_budget and errors:
                logger.warning("Retry budget exhausted — skipping remaining providers.")
                break

        raise AllProvidersFailedError(errors)

    # ─── Streaming ───────────────────────────────────────────────────────

    async def safe_stream(
        self,
        request: CompletionRequest,
        stop_event: Optional[asyncio.Event] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Smart resilient streaming.

        Args:
            request:      Completion request.
            stop_event:   asyncio.Event — set to stop stream cleanly at next chunk.
            retry_policy: RetryPolicy(max_retries=2, retry_delay=1.0) — configurable.

        Smart retry behavior:
            - If current provider has more keys → rotate key immediately (no sleep)
            - If no more keys → wait retry_delay, try next provider in fallback chain
            - If all providers exhausted and partial text generated → return what we have
        """
        policy = retry_policy or self._default_policy()
        state = SmartRetryState(policy)
        route = self.router.get_route(request.model)
        errors: List[LLMCycleError] = []
        generated_so_far = ""
        _stopped = False

        for provider_name, model in route:
            if provider_name not in self.providers:
                continue

            provider = self.providers[provider_name]
            keys_tried = 0
            max_keys_to_try = max(policy.max_retries + 1, self.key_manager.key_count(provider_name)["total"])

            while keys_tried < max_keys_to_try:
                key = self.key_manager.get_next_key(provider_name)
                if not key:
                    break
                keys_tried += 1

                req = request.model_copy(deep=True)
                req.model = model or request.model
                req.stream = True

                # Inject partial context on failover (SCENARIO 1)
                if generated_so_far:
                    req.messages = list(request.messages) + [
                        Message(role="assistant", content=generated_so_far),
                        Message(
                            role="user",
                            content="Continue your response exactly from where you stopped. Do not repeat anything.",
                        ),
                    ]

                try:
                    logger.info(
                        f"[{provider_name}] Streaming model={req.model} "
                        f"key#{keys_tried} "
                        f"retry_budget={policy.max_retries - state.retries_used} "
                        f"chars_so_far={len(generated_so_far)}"
                    )

                    async for chunk in provider.generate_stream(req, key):

                        # SCENARIO 3a: External stop signal
                        if stop_event and stop_event.is_set():
                            logger.info(f"[{provider_name}] Stopped via stop_event after {len(generated_so_far)} chars.")
                            _stopped = True
                            return

                        generated_so_far += chunk

                        try:
                            yield chunk
                        except GeneratorExit:
                            # SCENARIO 3b: Consumer broke out of `async for`
                            logger.info(f"[{provider_name}] GeneratorExit after {len(generated_so_far)} chars.")
                            _stopped = True
                            return

                    self.key_manager.report_success(provider_name, key)
                    return  # full stream complete

                except asyncio.CancelledError:
                    # SCENARIO 3c: Task cancelled
                    logger.info(f"[{provider_name}] CancelledError after {len(generated_so_far)} chars.")
                    _stopped = True
                    raise

                except ContentPolicyError:
                    # SCENARIO 4: Never retry
                    logger.error(f"[{provider_name}] Content policy — stopping.")
                    raise

                except AuthenticationError as e:
                    self.key_manager.report_error(provider_name, key, "auth")
                    errors.append(e)
                    continue  # disabled key, rotation skips it automatically

                except (RateLimitError, QuotaExceededError) as e:
                    err_type = "rate_limit" if isinstance(e, RateLimitError) else "quota"
                    self.key_manager.report_error(provider_name, key, err_type)
                    errors.append(e)
                    has_alt = self._has_alt_key(provider_name)
                    await state.wait_if_needed(provider_name, has_alt)
                    if has_alt:
                        continue  # rotate key, retry same provider
                    break  # no alt keys → next provider

                except LLMCycleError as e:
                    self.key_manager.report_error(provider_name, key, "server")
                    errors.append(e)
                    if generated_so_far:
                        logger.warning(
                            f"[{provider_name}] Stream interrupted at {len(generated_so_far)} chars — "
                            f"failing over with context."
                        )
                    has_alt = self._has_alt_key(provider_name)
                    await state.wait_if_needed(provider_name, has_alt)
                    if has_alt:
                        continue
                    break

                except Exception as e:
                    logger.error(f"[{provider_name}] Unexpected: {e}")
                    errors.append(LLMCycleError(str(e), provider=provider_name))
                    break

            if not state.has_budget and errors:
                logger.warning("Retry budget exhausted — stopping provider chain.")
                break

        if not _stopped:
            if not generated_so_far:
                raise AllProvidersFailedError(errors)
            else:
                logger.error(f"All providers exhausted. {len(generated_so_far)} chars already returned.")
