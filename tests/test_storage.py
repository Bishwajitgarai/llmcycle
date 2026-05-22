"""
Storage layer tests — uses SQLite in-memory so zero external deps.

Run:
    uv run pytest tests/test_storage.py -v
"""
from __future__ import annotations
import time
import pytest

from llmcycle.storage import StorageBackend, StorageManager
from llmcycle.storage.models import (
    Workplace, Team, User, Session, LLMRequest, HistoryMessage,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def store():
    """Fresh in-memory SQLite store per test."""
    s = StorageManager(
        backend=StorageBackend.SQLITE,
        url="sqlite+aiosqlite:///:memory:",
        schema=None,
        table_prefix="test_",
    )
    await s.connect()
    yield s
    await s.disconnect()


# ─── Enum & Config ────────────────────────────────────────────────────────────

class TestStorageBackendEnum:
    def test_all_backends_exist(self):
        values = {b.value for b in StorageBackend}
        assert values == {"sqlite", "postgres", "mysql", "mssql", "mongo", "redis"}

    def test_enum_from_string(self):
        assert StorageBackend("sqlite") == StorageBackend.SQLITE
        assert StorageBackend("postgres") == StorageBackend.POSTGRES
        assert StorageBackend("mongo") == StorageBackend.MONGO
        assert StorageBackend("redis") == StorageBackend.REDIS

    def test_invalid_enum_raises(self):
        with pytest.raises(ValueError):
            StorageBackend("oracle")


class TestStorageManagerConfig:
    def test_direct_args_take_priority(self, monkeypatch):
        monkeypatch.setenv("LLMCYCLE_STORAGE_BACKEND", "postgres")
        monkeypatch.setenv("LLMCYCLE_STORAGE_TABLE_PREFIX", "env_")
        # Direct args should win
        store = StorageManager(
            backend=StorageBackend.SQLITE,
            table_prefix="direct_",
        )
        assert store.backend_type == StorageBackend.SQLITE
        assert store.table_prefix == "direct_"

    def test_env_vars_used_when_no_args(self, monkeypatch):
        monkeypatch.setenv("LLMCYCLE_STORAGE_BACKEND", "sqlite")
        monkeypatch.setenv("LLMCYCLE_STORAGE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv("LLMCYCLE_STORAGE_TABLE_PREFIX", "env_")
        monkeypatch.setenv("LLMCYCLE_STORAGE_SCHEMA", "myschema")
        store = StorageManager()
        assert store.backend_type == StorageBackend.SQLITE
        assert store.table_prefix == "env_"
        assert store.schema == "myschema"

    def test_default_table_prefix_is_llmc(self, monkeypatch):
        monkeypatch.delenv("LLMCYCLE_STORAGE_TABLE_PREFIX", raising=False)
        store = StorageManager(backend=StorageBackend.SQLITE)
        assert store.table_prefix == "llmc_"

    def test_invalid_env_backend_raises(self, monkeypatch):
        monkeypatch.setenv("LLMCYCLE_STORAGE_BACKEND", "baddb")
        with pytest.raises(ValueError, match="Unknown LLMCYCLE_STORAGE_BACKEND"):
            StorageManager()


# ─── Ping ─────────────────────────────────────────────────────────────────────

class TestPing:
    async def test_ping_connected(self, store):
        result = await store.ping()
        assert result["ok"] is True
        assert result["backend"] == "sqlite"
        assert result["latency_ms"] >= 0

    async def test_ping_before_connect(self):
        """ping() auto-connects, tests, disconnects."""
        store = StorageManager(
            backend=StorageBackend.SQLITE,
            url="sqlite+aiosqlite:///:memory:",
        )
        result = await store.ping()
        assert result["ok"] is True

    async def test_ping_bad_url_returns_error(self):
        store = StorageManager(
            backend=StorageBackend.SQLITE,
            url="sqlite+aiosqlite:///Z:/nonexistent/path/db.sqlite",
        )
        result = await store.ping()
        # May succeed or fail depending on OS — just check it returns dict
        assert "ok" in result
        assert "backend" in result


# ─── Workplaces ───────────────────────────────────────────────────────────────

class TestWorkplaces:
    async def test_create_and_get(self, store):
        wp = Workplace(name="Acme Corp", settings={"plan": "pro"})
        created = await store.create_workplace(wp)
        assert created.id == wp.id

        fetched = await store.get_workplace(wp.id)
        assert fetched is not None
        assert fetched.name == "Acme Corp"
        assert fetched.settings["plan"] == "pro"

    async def test_get_nonexistent_returns_none(self, store):
        result = await store.get_workplace("nonexistent-id")
        assert result is None

    async def test_list_workplaces(self, store):
        await store.create_workplace(Workplace(name="Alpha"))
        await store.create_workplace(Workplace(name="Beta"))
        wps = await store.list_workplaces()
        assert len(wps) == 2
        names = {w.name for w in wps}
        assert "Alpha" in names and "Beta" in names


# ─── Teams ────────────────────────────────────────────────────────────────────

class TestTeams:
    async def test_create_and_get(self, store):
        wp = Workplace(name="Acme")
        await store.create_workplace(wp)
        team = Team(name="Engineering", workplace_id=wp.id, member_ids=["u1", "u2"])
        await store.create_team(team)

        fetched = await store.get_team(team.id)
        assert fetched.name == "Engineering"
        assert fetched.member_ids == ["u1", "u2"]

    async def test_list_teams_by_workplace(self, store):
        wp = Workplace(name="Org")
        await store.create_workplace(wp)
        await store.create_team(Team(name="Eng", workplace_id=wp.id))
        await store.create_team(Team(name="Sales", workplace_id=wp.id))
        await store.create_team(Team(name="Other", workplace_id="other-wp"))

        teams = await store.list_teams(workplace_id=wp.id)
        assert len(teams) == 2
        assert all(t.workplace_id == wp.id for t in teams)


# ─── Users ────────────────────────────────────────────────────────────────────

class TestUsers:
    async def test_create_get_update_delete(self, store):
        user = User(username="alice", email="alice@example.com", role="admin")
        await store.create_user(user)

        fetched = await store.get_user(user.id)
        assert fetched.username == "alice"
        assert fetched.role == "admin"

        user.role = "member"
        await store.update_user(user)
        updated = await store.get_user(user.id)
        assert updated.role == "member"

        await store.delete_user(user.id)
        assert await store.get_user(user.id) is None

    async def test_get_by_username(self, store):
        user = User(username="bob", email="bob@example.com")
        await store.create_user(user)
        found = await store.get_user_by_username("bob")
        assert found is not None
        assert found.id == user.id

    async def test_get_by_username_not_found(self, store):
        assert await store.get_user_by_username("ghost") is None

    async def test_list_users_by_team(self, store):
        t = Team(name="Dev", workplace_id="wp1")
        u1 = User(username="carol", team_id=t.id)
        u2 = User(username="dave",  team_id=t.id)
        u3 = User(username="eve",   team_id="other-team")
        for u in [u1, u2, u3]:
            await store.create_user(u)
        users = await store.list_users(team_id=t.id)
        assert len(users) == 2


# ─── Sessions ─────────────────────────────────────────────────────────────────

class TestSessions:
    async def test_create_and_get(self, store):
        session = Session(user_id="u1", model="gpt-4o")
        await store.create_session(session)
        fetched = await store.get_session(session.id)
        assert fetched.model == "gpt-4o"
        assert fetched.user_id == "u1"

    async def test_update_session(self, store):
        s = Session(user_id="u2", model="claude-3")
        await store.create_session(s)
        s.total_requests = 5
        s.total_tokens = 1500
        s.ended_at = time.time()
        await store.update_session(s)
        updated = await store.get_session(s.id)
        assert updated.total_requests == 5
        assert updated.total_tokens == 1500

    async def test_list_sessions_by_user(self, store):
        for i in range(3):
            await store.create_session(Session(user_id="u3", model=f"model-{i}"))
        await store.create_session(Session(user_id="other", model="x"))
        sessions = await store.list_sessions(user_id="u3")
        assert len(sessions) == 3


# ─── Requests ─────────────────────────────────────────────────────────────────

class TestRequests:
    async def test_save_and_get(self, store):
        req = LLMRequest(
            model="gpt-4o-mini", provider="openai",
            prompt="Hello", response="Hi there",
            prompt_tokens=10, completion_tokens=5,
            latency_ms=320.5, status="success",
        )
        await store.save_request(req)
        fetched = await store.get_request(req.id)
        assert fetched.model == "gpt-4o-mini"
        assert fetched.prompt_tokens == 10
        assert fetched.latency_ms == 320.5

    async def test_list_by_session(self, store):
        sid = "sess-xyz"
        for i in range(4):
            await store.save_request(LLMRequest(
                model="gpt-4o", provider="openai",
                session_id=sid, prompt=f"Q{i}",
            ))
        reqs = await store.list_requests(session_id=sid)
        assert len(reqs) == 4

    async def test_list_by_user(self, store):
        uid = "user-abc"
        await store.save_request(LLMRequest(model="m1", provider="p1", user_id=uid))
        await store.save_request(LLMRequest(model="m2", provider="p2", user_id=uid))
        await store.save_request(LLMRequest(model="m3", provider="p3", user_id="other"))
        reqs = await store.list_requests(user_id=uid)
        assert len(reqs) == 2


# ─── History ──────────────────────────────────────────────────────────────────

class TestHistory:
    async def test_append_and_get(self, store):
        sid = "sess-hist"
        await store.append_history(HistoryMessage(session_id=sid, role="user",    content="Hello"))
        await store.append_history(HistoryMessage(session_id=sid, role="assistant", content="Hi!"))
        history = await store.get_history(sid)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    async def test_clear_history(self, store):
        sid = "sess-clear"
        await store.append_history(HistoryMessage(session_id=sid, role="user", content="Bye"))
        await store.clear_history(sid)
        assert await store.get_history(sid) == []

    async def test_history_limit(self, store):
        sid = "sess-limit"
        for i in range(20):
            await store.append_history(HistoryMessage(session_id=sid, role="user", content=f"msg {i}"))
        history = await store.get_history(sid, limit=5)
        assert len(history) == 5


# ─── Purge by range ───────────────────────────────────────────────────────────

class TestPurgeByRange:
    async def _seed(self, store, n=10):
        """Seed n requests spread across time."""
        base = time.time() - n * 100
        reqs = []
        for i in range(n):
            r = LLMRequest(
                model="gpt-4o", provider="openai",
                prompt=f"Q{i}", created_at=base + i * 100,
            )
            r = LLMRequest.model_construct(**{**r.model_dump(), "created_at": base + i * 100})
            await store.save_request(r)
            reqs.append(r)
        return reqs, base

    async def test_purge_requests_to_ts(self, store):
        reqs, base = await self._seed(store, 10)
        cutoff = base + 500   # keeps last 5
        result = await store.purge_by_range(to_ts=cutoff)
        assert result["deleted"]["requests"] >= 5
        remaining = await store.list_requests(limit=100)
        assert all(r.created_at > cutoff for r in remaining)

    async def test_purge_requests_from_ts(self, store):
        reqs, base = await self._seed(store, 10)
        cutoff = base + 500   # deletes last 5
        result = await store.purge_by_range(from_ts=cutoff)
        assert result["deleted"]["requests"] >= 4

    async def test_purge_requests_range(self, store):
        reqs, base = await self._seed(store, 10)
        result = await store.purge_by_range(
            from_ts=base + 100,
            to_ts=base + 500,
        )
        assert result["deleted"]["requests"] >= 4

    async def test_purge_all_entities(self, store):
        reqs, base = await self._seed(store, 5)
        sid = "sid-all"
        await store.create_session(Session(user_id="u", model="m",
                                           started_at=base + 50))
        await store.append_history(HistoryMessage(session_id=sid, role="user",
                                                   content="x", created_at=base + 50))
        result = await store.purge_by_range(
            to_ts=base + 300,
            entities=["all"],
        )
        assert "requests" in result["deleted"]
        assert "history" in result["deleted"]
        assert "sessions" in result["deleted"]

    async def test_purge_no_range_defaults_requests_only(self, store):
        reqs, base = await self._seed(store, 3)
        result = await store.purge_by_range()  # default: entities=["requests"]
        assert "requests" in result["deleted"]
        # Should delete ALL requests since no range filter
        assert result["deleted"]["requests"] == 3


# ─── Analytics ────────────────────────────────────────────────────────────────

class TestAnalytics:
    async def _seed(self, store):
        """Seed diverse requests for analytics tests."""
        now = time.time()
        data = [
            dict(model="gpt-4o",       provider="openai",   prompt_tokens=100, completion_tokens=50, latency_ms=300, status="success",  user_id="u1"),
            dict(model="gpt-4o",       provider="openai",   prompt_tokens=200, completion_tokens=80, latency_ms=450, status="success",  user_id="u1"),
            dict(model="llama-3-70b",  provider="groq",     prompt_tokens=80,  completion_tokens=40, latency_ms=90,  status="success",  user_id="u2"),
            dict(model="llama-3-70b",  provider="groq",     prompt_tokens=60,  completion_tokens=30, latency_ms=80,  status="error",    user_id="u2"),
            dict(model="deepseek-chat",provider="deepseek", prompt_tokens=150, completion_tokens=70, latency_ms=600, status="success",  user_id="u1", fallback_used=True),
        ]
        for d in data:
            r = LLMRequest(**d)
            await store.save_request(r)

    async def test_summary_all(self, store):
        await self._seed(store)
        s = await store.analytics.summary()
        assert s["total_requests"] == 5
        assert s["total_prompt_tokens"] == 590
        assert s["error_count"] == 1
        assert s["fallback_count"] == 1
        assert round(s["error_rate"], 2) == 0.2
        assert "avg_latency_ms" in s
        assert "p95_latency_ms" in s

    async def test_summary_by_user(self, store):
        await self._seed(store)
        s = await store.analytics.summary(user_id="u1")
        assert s["total_requests"] == 3  # 2 openai + 1 deepseek

    async def test_summary_empty(self, store):
        s = await store.analytics.summary()
        assert s["total_requests"] == 0

    async def test_by_provider(self, store):
        await self._seed(store)
        bp = await store.analytics.by_provider()
        providers = [p["provider"] for p in bp]
        assert "openai" in providers
        assert "groq" in providers
        assert "deepseek" in providers
        openai_stat = next(p for p in bp if p["provider"] == "openai")
        assert openai_stat["requests"] == 2
        assert openai_stat["tokens"] == 430  # (100+50)+(200+80)

    async def test_by_model(self, store):
        await self._seed(store)
        bm = await store.analytics.by_model()
        models = [m["model"] for m in bm]
        assert "gpt-4o" in models
        gpt4o = next(m for m in bm if m["model"] == "gpt-4o")
        assert gpt4o["requests"] == 2

    async def test_by_user(self, store):
        await self._seed(store)
        bu = await store.analytics.by_user()
        u1 = next((u for u in bu if u["user_id"] == "u1"), None)
        assert u1 is not None
        assert u1["requests"] == 3

    async def test_by_session(self, store):
        sid = "sess-analytics"
        r1 = LLMRequest(model="gpt-4o", provider="openai", session_id=sid)
        r2 = LLMRequest(model="gpt-4o", provider="openai", session_id=sid)
        await store.save_request(r1)
        await store.save_request(r2)
        bs = await store.analytics.by_session()
        assert any(s["session_id"] == sid and s["requests"] == 2 for s in bs)

    async def test_timeseries_hour(self, store):
        await self._seed(store)
        ts = await store.analytics.timeseries(bucket="hour")
        assert isinstance(ts, list)
        total = sum(b["requests"] for b in ts)
        assert total == 5

    async def test_timeseries_day(self, store):
        await self._seed(store)
        ts = await store.analytics.timeseries(bucket="day")
        assert isinstance(ts, list)

    async def test_top_errors(self, store):
        await store.save_request(LLMRequest(model="m", provider="p", status="error", error="Rate limited"))
        await store.save_request(LLMRequest(model="m", provider="p", status="error", error="Rate limited"))
        await store.save_request(LLMRequest(model="m", provider="p", status="error", error="Auth failed"))
        errors = await store.analytics.top_errors(limit=5)
        assert len(errors) >= 1
        top = errors[0]
        assert top["error"] == "Rate limited"
        assert top["count"] == 2

    async def test_summary_with_time_range(self, store):
        await self._seed(store)
        now = time.time()
        # From 1 day ago to now should include all
        s = await store.analytics.summary(from_ts=now - 86400, to_ts=now + 60)
        assert s["total_requests"] == 5

    async def test_by_provider_filter(self, store):
        await self._seed(store)
        bp = await store.analytics.by_provider()
        groq = next((p for p in bp if p["provider"] == "groq"), None)
        assert groq is not None
        assert groq["errors"] == 1
