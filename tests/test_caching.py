"""
Unit tests for pluggable caching layer in LLMCycle.
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from llmcycle.client import LLMCycle
from llmcycle.schema import CompletionResponse, Message
from llmcycle.core.cache import InMemoryCache, SQLCache
from llmcycle.providers.base import LLMProvider

def make_response(content="Hello!") -> CompletionResponse:
    return CompletionResponse(
        id="test-id",
        provider="openai",
        model="gpt-4o",
        content=content,
        prompt_tokens=5,
        completion_tokens=5,
        latency_ms=10.0,
    )


@pytest.mark.asyncio
class TestInMemoryCache:
    async def test_set_and_get(self):
        cache = InMemoryCache(max_size=3)
        res = make_response()
        await cache.set("k1", res, ttl=10)

        # Hit
        hit = await cache.get("k1")
        assert hit is not None
        assert hit.content == "Hello!"

        # Miss
        miss = await cache.get("k2")
        assert miss is None

    async def test_ttl_expiration(self):
        cache = InMemoryCache(max_size=3)
        res = make_response()
        await cache.set("k1", res, ttl=0.01)

        await asyncio.sleep(0.02)
        hit = await cache.get("k1")
        assert hit is None

    async def test_lru_eviction(self):
        cache = InMemoryCache(max_size=2)
        res1 = make_response("one")
        res2 = make_response("two")
        res3 = make_response("three")

        await cache.set("k1", res1, ttl=10)
        await cache.set("k2", res2, ttl=10)
        await cache.set("k3", res3, ttl=10)

        # k1 should be evicted since capacity is 2
        assert await cache.get("k1") is None
        assert (await cache.get("k2")).content == "two"
        assert (await cache.get("k3")).content == "three"


@pytest.mark.asyncio
class TestSQLCache:
    async def test_sql_cache_operations(self):
        # sqlite in-memory database
        cache = SQLCache("sqlite+aiosqlite:///:memory:")
        res = make_response()
        await cache.set("k1", res, ttl=10)

        # Hit
        hit = await cache.get("k1")
        assert hit is not None
        assert hit.content == "Hello!"

        # Miss
        miss = await cache.get("k2")
        assert miss is None

        # Stats
        stats = await cache.stats()
        assert stats["total"] == 1
        assert stats["active"] == 1

        # Clear
        cleared = await cache.clear()
        assert cleared == 1
        assert await cache.get("k1") is None


@pytest.mark.asyncio
class TestLLMCycleCacheIntegration:
    async def test_client_cache_integration(self):
        mock_provider = AsyncMock(spec=LLMProvider)
        mock_provider.generate.return_value = make_response("Inference result")

        cache = InMemoryCache()
        client = LLMCycle(cache=cache)
        client._providers["openai"] = mock_provider
        client.key_manager.add_key("openai", "sk-test")

        # First call: cache miss
        r1 = await client.complete("openai/gpt-4o", prompt="Cache test", cache_ttl=50)
        assert r1.content == "Inference result"
        assert mock_provider.generate.call_count == 1

        # Second call: cache hit
        r2 = await client.complete("openai/gpt-4o", prompt="Cache test", cache_ttl=50)
        assert r2.content == "Inference result"
        # call count should still be 1 (provider not called)
        assert mock_provider.generate.call_count == 1
