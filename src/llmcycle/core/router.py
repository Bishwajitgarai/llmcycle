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
from typing import Any, List, Dict, Optional, Tuple

from llmcycle.utils import parse_model

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    PRIORITY       = "priority"        # follow explicit sort order
    ROUND_ROBIN    = "round_robin"     # cycle across all providers
    LOWEST_LATENCY = "lowest_latency"  # pick the statistically fastest
    CANARY         = "canary"          # canary percentage traffic splits
    WEIGHTED       = "weighted"        # weight-based routing
    COST_OPTIMIZED = "cost_optimized"  # route to cheapest provider first


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
          "logical-model": {"openai/gpt-4o-mini": 0.85, "groq/llama-3.1-70b": 0.15}  # Canary/Weighted routing
        }
    """

    def __init__(
        self,
        fallbacks: Optional[Dict[str, Any]] = None,
        strategy: RoutingStrategy = RoutingStrategy.PRIORITY,
        pricing: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        self.fallbacks = fallbacks or {}
        self.strategy  = strategy
        self.pricing   = pricing or {}   # shared with client — same DEFAULT_PRICING dict
        self.latency   = LatencyTracker()
        self._rr_index: Dict[str, int] = {}
        self._lock     = threading.Lock()

    def get_route(self, model: str) -> List[Tuple[str, str]]:
        """
        Returns ordered list of (provider, model) tuples to try.
        Input model format: "provider/model" or just "model".
        """
        # Under CANARY or WEIGHTED strategies, look up if a dictionary weight split is configured
        if self.strategy in (RoutingStrategy.CANARY, RoutingStrategy.WEIGHTED):
            fb_val = self.fallbacks.get(model)
            if isinstance(fb_val, dict) and fb_val:
                import random
                choices = list(fb_val.keys())
                weights = list(fb_val.values())
                selected = random.choices(choices, weights=weights, k=1)[0]

                # Make selected primary, followed by the rest as fallback order sorted by weight descending
                remaining = [c for c in choices if c != selected]
                remaining.sort(key=lambda c: fb_val[c], reverse=True)

                candidates = [parse_model(selected)] + [parse_model(r) for r in remaining]
                return candidates

        primary_provider, primary_model = parse_model(model)
        candidates = [(primary_provider, primary_model)]

        # Look up fallbacks by full key ("openai/gpt-4o") or provider key ("openai")
        fb_key = model if "/" in model else primary_provider
        fb_list = self.fallbacks.get(fb_key) or self.fallbacks.get(primary_provider, [])

        # If it's a list, treat normally. If it's a dict, use keys.
        if isinstance(fb_list, dict):
            # Sort dict keys by weight descending as default ordering
            fb_keys_sorted = list(fb_list.keys())
            fb_keys_sorted.sort(key=lambda k: fb_list[k], reverse=True)
            fb_list = fb_keys_sorted

        for fb in fb_list:
            candidates.append(parse_model(fb))

        if self.strategy == RoutingStrategy.LOWEST_LATENCY:
            candidates.sort(key=lambda t: self.latency.get(t[0]))

        elif self.strategy == RoutingStrategy.ROUND_ROBIN:
            with self._lock:
                idx = self._rr_index.get(model, 0)
                candidates = candidates[idx:] + candidates[:idx]
                self._rr_index[model] = (idx + 1) % len(candidates)

        elif self.strategy == RoutingStrategy.COST_OPTIMIZED:
            candidates.sort(key=lambda t: self._input_cost(t[1] or t[0]))

        return candidates

    def _input_cost(self, model_name: str) -> float:
        """
        Look up the input cost (USD/1K tokens) for a model using the same
        partial-key match as client._get_pricing.
        Unknown models sort last (float inf).
        """
        name_lower = model_name.lower()
        for key, price in self.pricing.items():
            if key in name_lower:
                return price.get("input", float("inf"))
        return float("inf")

    def record_latency(self, provider: str, latency_ms: float):
        self.latency.record(provider, latency_ms)
