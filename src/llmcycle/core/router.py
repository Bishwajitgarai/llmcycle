"""
ModelRouter - Sort-Order Routing & Fallback
============================================
Supports:
  - Priority-ordered fallback chains per model/provider
  - RoutingStrategy enum: PRIORITY | ROUND_ROBIN | LOWEST_LATENCY
  - Latency tracking with EWMA (exponentially weighted moving average)
"""
from __future__ import annotations
import time
import threading
import logging
from enum import Enum
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    PRIORITY       = "priority"        # follow explicit sort order
    ROUND_ROBIN    = "round_robin"     # cycle across all providers
    LOWEST_LATENCY = "lowest_latency"  # pick the statistically fastest


class LatencyTracker:
    """Per-provider EWMA latency tracking."""
    ALPHA = 0.3  # smoothing factor

    def __init__(self):
        self._latencies: Dict[str, float] = {}
        self._lock = threading.Lock()

    def record(self, provider: str, latency_ms: float):
        with self._lock:
            prev = self._latencies.get(provider, latency_ms)
            self._latencies[provider] = self.ALPHA * latency_ms + (1 - self.ALPHA) * prev

    def get(self, provider: str) -> float:
        return self._latencies.get(provider, 999999.0)

    def all(self) -> Dict[str, float]:
        return dict(self._latencies)


class ModelRouter:
    """
    Determines the ordered list of (provider, model) pairs to try for a request.

    Fallback config format:
        {
          "openai/gpt-4o": ["anthropic/claude-3-5-sonnet", "groq/llama-3.1-70b"],
          "groq": ["together", "fireworks"],   # provider-level fallback
        }
    """

    def __init__(
        self,
        fallbacks: Optional[Dict[str, List[str]]] = None,
        strategy: RoutingStrategy = RoutingStrategy.PRIORITY,
    ):
        self.fallbacks = fallbacks or {}
        self.strategy = strategy
        self.latency = LatencyTracker()
        self._rr_index: Dict[str, int] = {}
        self._lock = threading.Lock()

    def get_route(self, model: str) -> List[Tuple[str, str]]:
        """
        Returns ordered list of (provider, model) tuples to try.
        Input model format: "provider/model" or just "model".
        """
        primary_provider, primary_model = self._parse(model)
        candidates = [(primary_provider, primary_model)]

        # Look up fallbacks by full key ("openai/gpt-4o") or provider key ("openai")
        fb_key = model if "/" in model else primary_provider
        fb_list = self.fallbacks.get(fb_key) or self.fallbacks.get(primary_provider, [])

        for fb in fb_list:
            candidates.append(self._parse(fb))

        if self.strategy == RoutingStrategy.LOWEST_LATENCY:
            candidates.sort(key=lambda t: self.latency.get(t[0]))

        elif self.strategy == RoutingStrategy.ROUND_ROBIN:
            with self._lock:
                idx = self._rr_index.get(model, 0)
                candidates = candidates[idx:] + candidates[:idx]
                self._rr_index[model] = (idx + 1) % len(candidates)

        return candidates

    def record_latency(self, provider: str, latency_ms: float):
        self.latency.record(provider, latency_ms)

    @staticmethod
    def _parse(model_str: str) -> Tuple[str, str]:
        """
        "openai/gpt-4o" → ("openai", "gpt-4o")
        "gpt-4o"         → ("openai", "gpt-4o")   ← infer provider
        "groq"           → ("groq",  "")
        """
        if "/" in model_str:
            parts = model_str.split("/", 1)
            return parts[0].lower(), parts[1]
        # Bare model name — return as-is; caller resolves provider
        return model_str.lower(), model_str
