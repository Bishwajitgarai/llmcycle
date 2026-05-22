"""
Comprehensive LLMCycle test suite.
All tests use mocks — no real API calls needed.
"""
import asyncio
import time
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from llmcycle.core.keys import KeyManager, KeyStatus
from llmcycle.core.router import ModelRouter, RoutingStrategy
from llmcycle.core.stream import StreamResilienceManager, RetryPolicy
from llmcycle.core.errors import (
    RateLimitError, AuthenticationError, QuotaExceededError,
    ContentPolicyError, ProviderError, AllProvidersFailedError,
    classify_http_error,
)
from llmcycle.schema import CompletionRequest, CompletionResponse, Message
from llmcycle.providers.base import LLMProvider


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_request(model="openai/gpt-4o", prompt="Hello") -> CompletionRequest:
    return CompletionRequest(
        model=model,
        messages=[Message(role="user", content=prompt)],
    )

def make_response(provider="openai", model="gpt-4o") -> CompletionResponse:
    return CompletionResponse(
        id="test-id", provider=provider, model=model,
        content="Hello!", latency_ms=100,
    )

async def good_stream(chunks=("Hello", " world", "!")):
    for c in chunks:
        yield c

async def failing_stream(fail_after=2):
    chunks = ["chunk1", " chunk2", " chunk3", " chunk4"]
    for i, c in enumerate(chunks):
        if i == fail_after:
            raise ProviderError("Connection dropped", provider="test")
        yield c


# ─── KeyManager Tests ────────────────────────────────────────────────────────

class TestKeyManager:
    def test_add_and_roundrobin(self):
        km = KeyManager()
        km.add_keys("openai", ["sk-1", "sk-2", "sk-3"])
        assert km.get_next_key("openai") == "sk-1"
        assert km.get_next_key("openai") == "sk-2"
        assert km.get_next_key("openai") == "sk-3"
        assert km.get_next_key("openai") == "sk-1"  # wraps

    def test_no_duplicate_keys(self):
        km = KeyManager()
        km.add_key("openai", "sk-dup")
        km.add_key("openai", "sk-dup")
        assert km.key_count("openai")["total"] == 1

    def test_rate_limit_skips_key(self):
        km = KeyManager()
        km.add_keys("openai", ["sk-1", "sk-2"])
        km.report_error("openai", "sk-1", "rate_limit")
        # sk-1 should be skipped
        assert km.get_next_key("openai") == "sk-2"
        assert km.get_next_key("openai") == "sk-2"  # only sk-2 active

    def test_auth_error_disables_key_permanently(self):
        km = KeyManager()
        km.add_key("openai", "sk-bad")
        km.report_error("openai", "sk-bad", "auth")
        assert km.get_next_key("openai") is None

    def test_quota_error_sets_long_cooldown(self):
        km = KeyManager()
        km.add_key("openai", "sk-1")
        km.report_error("openai", "sk-1", "quota")
        rec = km._find("openai", "sk-1")
        assert rec.status == KeyStatus.QUOTA_EXHAUSTED
        assert rec.rate_limit_until > time.time()

    def test_key_hint_masks_key(self):
        km = KeyManager()
        km.add_key("openai", "sk-abc1234567890")
        stats = km.get_stats("openai")
        assert "sk-abc" in stats[0]["hint"]
        assert "sk-abc1234567890" not in stats[0]["hint"]

    def test_no_keys_returns_none(self):
        km = KeyManager()
        assert km.get_next_key("nonexistent") is None

    def test_key_count(self):
        km = KeyManager()
        km.add_keys("groq", ["k1", "k2", "k3"])
        km.report_error("groq", "k1", "auth")
        counts = km.key_count("groq")
        assert counts["total"] == 3
        assert counts["active"] == 2
        assert counts["invalid"] == 1

    def test_auto_recovery_after_cooldown(self):
        km = KeyManager()
        km.add_key("groq", "sk-rec")
        km.report_error("groq", "sk-rec", "rate_limit")
        rec = km._find("groq", "sk-rec")
        # Simulate cooldown expired
        rec.rate_limit_until = time.time() - 1
        # Should auto-recover on next get_next_key
        key = km.get_next_key("groq")
        assert key == "sk-rec"
        assert rec.status == KeyStatus.ACTIVE


# ─── Router Tests ────────────────────────────────────────────────────────────

class TestModelRouter:
    def test_priority_route_no_fallbacks(self):
        router = ModelRouter()
        route = router.get_route("openai/gpt-4o")
        assert route[0] == ("openai", "gpt-4o")

    def test_priority_route_with_fallbacks(self):
        router = ModelRouter(fallbacks={
            "openai/gpt-4o": ["groq/llama-3.1-70b", "together/mixtral"]
        })
        route = router.get_route("openai/gpt-4o")
        assert route[0] == ("openai", "gpt-4o")
        assert route[1] == ("groq", "llama-3.1-70b")
        assert route[2] == ("together", "mixtral")

    def test_provider_level_fallback(self):
        router = ModelRouter(fallbacks={"openai": ["groq", "together"]})
        route = router.get_route("openai/gpt-4o")
        providers = [p for p, _ in route]
        assert "groq" in providers
        assert "together" in providers

    def test_latency_tracker(self):
        router = ModelRouter(strategy=RoutingStrategy.LOWEST_LATENCY)
        router.record_latency("openai", 300.0)
        router.record_latency("groq", 50.0)
        assert router.latency.get("groq") < router.latency.get("openai")

    def test_parse_model_string(self):
        assert ModelRouter._parse("openai/gpt-4o") == ("openai", "gpt-4o")
        assert ModelRouter._parse("gpt-4o") == ("gpt-4o", "gpt-4o")
        assert ModelRouter._parse("groq") == ("groq", "groq")


# ─── Error Classification Tests ───────────────────────────────────────────────

class TestErrorClassification:
    def test_401_is_auth_error(self):
        e = classify_http_error(401, "Unauthorized", "openai", "gpt-4o")
        assert isinstance(e, AuthenticationError)

    def test_429_is_rate_limit(self):
        e = classify_http_error(429, "Too many requests", "openai", "gpt-4o")
        assert isinstance(e, RateLimitError)

    def test_429_quota_message(self):
        e = classify_http_error(429, "quota exceeded", "openai", "gpt-4o")
        assert isinstance(e, QuotaExceededError)

    def test_402_is_quota(self):
        e = classify_http_error(402, "Payment Required", "openai", "gpt-4o")
        assert isinstance(e, QuotaExceededError)

    def test_400_content_policy(self):
        e = classify_http_error(400, "content_policy violation", "openai", "gpt-4o")
        assert isinstance(e, ContentPolicyError)

    def test_400_bad_request(self):
        e = classify_http_error(400, "Invalid model", "openai", "gpt-4o")
        assert isinstance(e, ProviderError)

    def test_500_server_error(self):
        e = classify_http_error(500, "Internal Server Error", "openai", "gpt-4o")
        assert isinstance(e, ProviderError)


# ─── StreamResilienceManager Tests ───────────────────────────────────────────

@pytest.mark.asyncio
class TestStreamResilience:
    def _make_manager(self, provider_map: dict):
        """Build a manager with mocked providers."""
        km = KeyManager()
        router = ModelRouter()

        for name, provider_obj in provider_map.items():
            km.add_key(name, f"sk-{name}-test")

        return StreamResilienceManager(router, km, provider_map)

    async def test_complete_success(self):
        mock_provider = AsyncMock(spec=LLMProvider)
        mock_provider.generate.return_value = make_response("openai", "gpt-4o")

        mgr = self._make_manager({"openai": mock_provider})
        result = await mgr.complete(make_request("openai/gpt-4o"))
        assert result.content == "Hello!"
        assert result.provider == "openai"

    async def test_stream_full_success(self):
        async def _gen(*args, **kwargs):
            for c in ("Hello", " world", "!"):
                yield c

        mock_provider = MagicMock()  # no spec — allows raw async generator side_effect
        mock_provider.generate_stream.side_effect = _gen

        mgr = self._make_manager({"openai": mock_provider})
        chunks = []
        async for chunk in mgr.safe_stream(make_request("openai/gpt-4o")):
            chunks.append(chunk)

        assert "".join(chunks) == "Hello world!"

    async def test_stream_failover_on_connection_drop(self):
        """Primary provider drops mid-stream → failover continues on secondary."""
        async def _primary_gen(*args, **kwargs):
            yield "chunk1"
            yield " chunk2"
            raise ProviderError("Connection dropped", provider="primary")

        async def _secondary_gen(*args, **kwargs):
            yield " resumed"
            yield " ok"

        primary = MagicMock()  # no spec — allows raw async generator
        primary.generate_stream.side_effect = _primary_gen

        secondary = MagicMock()
        secondary.generate_stream.side_effect = _secondary_gen

        km = KeyManager()
        km.add_key("primary", "sk-p")
        km.add_key("secondary", "sk-s")

        router = ModelRouter(fallbacks={"primary/model": ["secondary/model"]})
        mgr = StreamResilienceManager(router, km, {
            "primary": primary,
            "secondary": secondary,
        })

        chunks = []
        async for chunk in mgr.safe_stream(make_request("primary/model")):
            chunks.append(chunk)

        full = "".join(chunks)
        assert "chunk1" in full     # from primary
        assert "resumed" in full    # from secondary

    async def test_complete_rotates_key_on_rate_limit(self):
        """On 429, manager should rotate to next key before failing over."""
        mock_provider = AsyncMock(spec=LLMProvider)
        mock_provider.generate.side_effect = [
            RateLimitError("429", provider="groq", model="llama"),
            make_response("groq", "llama"),  # second key succeeds
        ]

        km = KeyManager()
        km.add_keys("groq", ["sk-1", "sk-2"])
        router = ModelRouter()
        mgr = StreamResilienceManager(router, km, {"groq": mock_provider})

        result = await mgr.complete(make_request("groq/llama"),
                                    retry_policy=RetryPolicy(max_retries=3))
        assert result.content == "Hello!"

    async def test_auth_error_disables_key(self):
        """401 should permanently disable the key and try next provider."""
        mock = AsyncMock(spec=LLMProvider)
        mock.generate.side_effect = AuthenticationError("401", provider="openai", model="gpt-4o")

        km = KeyManager()
        km.add_key("openai", "sk-bad")
        router = ModelRouter()
        mgr = StreamResilienceManager(router, km, {"openai": mock})

        with pytest.raises(AllProvidersFailedError):
            await mgr.complete(make_request("openai/gpt-4o"))

        rec = km._find("openai", "sk-bad")
        assert rec.status == KeyStatus.INVALID

    async def test_content_policy_never_retried(self):
        """ContentPolicyError must propagate immediately without retry."""
        mock = AsyncMock(spec=LLMProvider)
        mock.generate.side_effect = ContentPolicyError("400 content", provider="openai", model="gpt-4o")

        km = KeyManager()
        km.add_keys("openai", ["sk-1", "sk-2", "sk-3"])
        router = ModelRouter()
        mgr = StreamResilienceManager(router, km, {"openai": mock})

        with pytest.raises(ContentPolicyError):
            await mgr.complete(make_request("openai/gpt-4o"))

        # Should only have been called once — no retries
        assert mock.generate.call_count == 1

    async def test_stop_event_halts_stream(self):
        """Setting stop_event mid-stream should exit cleanly."""
        async def _infinite_gen(*args, **kwargs):
            i = 0
            while True:
                yield f"chunk{i}"
                i += 1

        mock = MagicMock()  # no spec — allows raw async generator
        mock.generate_stream.side_effect = _infinite_gen

        km = KeyManager()
        km.add_key("openai", "sk-1")
        router = ModelRouter()
        mgr = StreamResilienceManager(router, km, {"openai": mock})

        stop = asyncio.Event()
        chunks = []

        async for chunk in mgr.safe_stream(make_request("openai/gpt-4o"), stop_event=stop):
            chunks.append(chunk)
            if len(chunks) == 3:
                stop.set()  # stop after 3 chunks

        assert len(chunks) == 3

    async def test_all_providers_failed_raises(self):
        """When all providers fail, AllProvidersFailedError should be raised."""
        mock = AsyncMock(spec=LLMProvider)
        mock.generate.side_effect = ProviderError("500", provider="openai", model="gpt-4o")

        km = KeyManager()
        km.add_key("openai", "sk-1")
        router = ModelRouter()
        mgr = StreamResilienceManager(router, km, {"openai": mock})

        with pytest.raises(AllProvidersFailedError) as exc_info:
            await mgr.complete(make_request("openai/gpt-4o"))

        assert len(exc_info.value.errors) > 0


# ─── RetryPolicy Tests ───────────────────────────────────────────────────────

class TestRetryPolicy:
    def test_default_values(self):
        p = RetryPolicy()
        assert p.max_retries == 2
        assert p.retry_delay == 1.0

    def test_custom_values(self):
        p = RetryPolicy(max_retries=5, retry_delay=2.5)
        assert p.max_retries == 5
        assert p.retry_delay == 2.5

    def test_budget_tracking(self):
        from llmcycle.core.stream import SmartRetryState
        state = SmartRetryState(RetryPolicy(max_retries=2))
        assert state.has_budget
        state.consume()
        assert state.has_budget
        state.consume()
        assert not state.has_budget
