"""
Client-Side Token Bucket Rate Limiting (Self-Throttling)
=========================================================
Thread-safe and async-safe token bucket rate limiters to track and enforce
RPM (Requests Per Minute) and TPM (Tokens Per Minute) client-side.
Auto-throttles requests via async queues to completely prevent provider 429s.
"""
from __future__ import annotations
import asyncio
import time
import logging
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TokenBucket:
    """A thread-safe Token Bucket for managing rate limits (RPM or TPM)."""

    def __init__(self, limit: float, window: float = 60.0):
        self.limit = limit
        self.window = window
        self.tokens = limit
        self.last_update = time.time()
        self.lock = threading.Lock()

    def _replenish(self):
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now
        added = elapsed * (self.limit / self.window)
        self.tokens = min(self.limit, self.tokens + added)

    def get_wait_time(self, tokens_needed: float) -> float:
        """
        Check and deduct tokens.
        If tokens are available, returns 0.0 immediately.
        If not, returns the duration in seconds the caller should sleep.
        """
        with self.lock:
            self._replenish()
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return 0.0

            # Calculate wait time needed to replenish the deficit
            deficit = tokens_needed - self.tokens
            fill_rate = self.limit / self.window
            wait_time = deficit / fill_rate

            # Reserve tokens for this caller (going negative is fair queueing)
            self.tokens -= tokens_needed
            return wait_time


class RateLimiter:
    """Enforces RPM and TPM rate limits together on a single endpoint/model."""

    def __init__(self, rpm_limit: Optional[int] = None, tpm_limit: Optional[int] = None):
        self.rpm_bucket = TokenBucket(rpm_limit) if rpm_limit else None
        self.tpm_bucket = TokenBucket(tpm_limit) if tpm_limit else None

    async def acquire(self, tokens: int = 1):
        """Acquire rate limiting capacity, sleeping if limits are breached."""
        wait_rpm = 0.0
        wait_tpm = 0.0

        if self.rpm_bucket:
            wait_rpm = self.rpm_bucket.get_wait_time(1)
        if self.tpm_bucket:
            wait_tpm = self.tpm_bucket.get_wait_time(tokens)

        max_wait = max(wait_rpm, wait_tpm)
        if max_wait > 0.0:
            logger.info(f"Self-throttling client rate limit: sleeping {max_wait:.2f}s...")
            await asyncio.sleep(max_wait)


class RateLimitManager:
    """Global manager for rate limiters by model and key."""

    def __init__(self, limits: Optional[Dict[str, Dict[str, int]]] = None):
        self.limits = limits or {}
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = threading.Lock()

    def get_limiter(self, model: str) -> RateLimiter:
        """Retrieve or construct the RateLimiter for a given model."""
        with self._lock:
            if model not in self._limiters:
                model_limits = self.limits.get(model, {})
                rpm = model_limits.get("rpm")
                tpm = model_limits.get("tpm")
                self._limiters[model] = RateLimiter(rpm, tpm)
            return self._limiters[model]
