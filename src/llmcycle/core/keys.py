"""
KeyManager - Production Multi-Key Rotation
==========================================
Supports:
 - Round-robin across multiple keys
 - Rate-limit cooldown per key (auto re-enable after cooldown)
 - Permanent disable on auth failure (401)
 - Per-key error tracking with thresholds
"""
from __future__ import annotations
import time
import threading
import hashlib
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

RATE_LIMIT_COOLDOWN_SECS = 60
QUOTA_COOLDOWN_SECS = 3600

class KeyStatus(Enum):
    ACTIVE      = "active"
    RATE_LIMITED = "rate_limited"   # 429 – temporary, retry after cooldown
    QUOTA_EXHAUSTED = "quota_exhausted"  # 402/429 quota – long cooldown
    INVALID     = "invalid"         # 401 – permanent disable
    DISABLED    = "disabled"        # manual disable

@dataclass
class KeyRecord:
    key: str
    provider: str
    status: KeyStatus = KeyStatus.ACTIVE
    total_requests: int = 0
    total_errors: int = 0
    consecutive_errors: int = 0
    rate_limit_until: float = 0.0
    added_at: float = field(default_factory=time.time)
    last_used: float = 0.0

    @property
    def key_hint(self) -> str:
        """Safe display: show first 6 and last 4 chars."""
        if len(self.key) <= 10:
            return "***"
        return f"{self.key[:6]}...{self.key[-4:]}"

    @property
    def is_usable(self) -> bool:
        if self.status == KeyStatus.ACTIVE:
            return True
        if self.status in (KeyStatus.RATE_LIMITED, KeyStatus.QUOTA_EXHAUSTED):
            return time.time() >= self.rate_limit_until
        return False


class KeyManager:
    """Thread-safe multi-key manager with auto rotation and error classification."""

    def __init__(self):
        self._lock = threading.Lock()
        # provider → list of KeyRecord (in insertion order for round-robin)
        self._keys: Dict[str, List[KeyRecord]] = {}
        # Round-robin pointer per provider
        self._indexes: Dict[str, int] = {}

    def add_key(self, provider: str, key: str) -> None:
        """Register one API key for a provider."""
        p = provider.lower()
        with self._lock:
            if p not in self._keys:
                self._keys[p] = []
                self._indexes[p] = 0
            # Don't add duplicates
            existing = {r.key for r in self._keys[p]}
            if key not in existing:
                self._keys[p].append(KeyRecord(key=key, provider=p))
                logger.debug(f"[{p}] Registered key {KeyRecord(key=key, provider=p).key_hint}")

    def add_keys(self, provider: str, keys: List[str]) -> None:
        for k in keys:
            self.add_key(provider, k)

    def get_next_key(self, provider: str) -> Optional[str]:
        """Round-robin rotation. Auto-recovers rate-limited keys after cooldown."""
        p = provider.lower()
        with self._lock:
            records = self._keys.get(p, [])
            if not records:
                return None

            n = len(records)
            start = self._indexes[p]

            for i in range(n):
                idx = (start + i) % n
                rec = records[idx]

                # Auto-recover temporarily banned keys
                if rec.status in (KeyStatus.RATE_LIMITED, KeyStatus.QUOTA_EXHAUSTED):
                    if time.time() >= rec.rate_limit_until:
                        rec.status = KeyStatus.ACTIVE
                        rec.consecutive_errors = 0
                        logger.info(f"[{p}] Key {rec.key_hint} auto-recovered from {rec.status.value}")

                if rec.is_usable:
                    self._indexes[p] = (idx + 1) % n
                    rec.last_used = time.time()
                    rec.total_requests += 1
                    return rec.key

            logger.warning(f"[{p}] No usable keys available!")
            return None

    def report_success(self, provider: str, key: str) -> None:
        rec = self._find(provider, key)
        if rec:
            rec.consecutive_errors = 0

    def report_error(self, provider: str, key: str, error_type: str) -> None:
        """
        error_type: "rate_limit" | "quota" | "auth" | "server" | "connection"
        """
        rec = self._find(provider, key)
        if not rec:
            return

        rec.total_errors += 1
        rec.consecutive_errors += 1

        if error_type == "auth":
            rec.status = KeyStatus.INVALID
            logger.warning(f"[{provider}] Key {rec.key_hint} permanently disabled (401 Auth)")

        elif error_type == "quota":
            rec.status = KeyStatus.QUOTA_EXHAUSTED
            rec.rate_limit_until = time.time() + QUOTA_COOLDOWN_SECS
            logger.warning(f"[{provider}] Key {rec.key_hint} quota exhausted. Retry after {QUOTA_COOLDOWN_SECS}s")

        elif error_type == "rate_limit":
            rec.status = KeyStatus.RATE_LIMITED
            rec.rate_limit_until = time.time() + RATE_LIMIT_COOLDOWN_SECS
            logger.warning(f"[{provider}] Key {rec.key_hint} rate limited. Retry after {RATE_LIMIT_COOLDOWN_SECS}s")

        elif error_type in ("server", "connection"):
            # Don't ban the key, just note the error
            logger.debug(f"[{provider}] Key {rec.key_hint} got {error_type} error (key kept active)")

    def get_stats(self, provider: str) -> List[dict]:
        p = provider.lower()
        with self._lock:
            return [
                {
                    "hint": r.key_hint,
                    "status": r.status.value,
                    "total_requests": r.total_requests,
                    "total_errors": r.total_errors,
                    "last_used": r.last_used,
                }
                for r in self._keys.get(p, [])
            ]

    def list_providers(self) -> List[str]:
        return list(self._keys.keys())

    def key_count(self, provider: str) -> dict:
        p = provider.lower()
        records = self._keys.get(p, [])
        return {
            "total": len(records),
            "active": sum(1 for r in records if r.is_usable),
            "invalid": sum(1 for r in records if r.status == KeyStatus.INVALID),
        }

    def has_active_keys(self, provider: str) -> bool:
        """Returns True if the provider has at least one usable key."""
        p = provider.lower()
        records = self._keys.get(p, [])
        return any(r.is_usable for r in records)

    def _find(self, provider: str, key: str) -> Optional[KeyRecord]:
        p = provider.lower()
        with self._lock:
            for rec in self._keys.get(p, []):
                if rec.key == key:
                    return rec
        return None
