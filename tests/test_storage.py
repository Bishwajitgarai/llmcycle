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
    ToolCall, RequestFeedback,
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
        assert StorageBackend("mysql") == StorageBackend.MYSQL
        assert StorageBackend("mssql") == StorageBackend.MSSQL

    def test_invalid_enum_raises(self):
        with pytest.raises(ValueError):
            StorageBackend("oracle")

    def test_all_six_members(self):
        assert len(StorageBackend) == 6


class TestStorageManagerConfig:
    def test_direct_args_take_priority(self, monkeypatch):
        monkeypatch.setenv("LLMCYCLE_STORAGE_BACKEND", "postgres")
        monkeypatch.setenv("LLMCYCLE_STORAGE_TABLE_PREFIX", "env_")
        store = StorageManager(backend=StorageBackend.SQLITE, table_prefix="direct_")
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

    def test_schema_default_is_none(self, monkeypatch):
        monkeypatch.delenv("LLMCYCLE_STORAGE_SCHEMA", raising=False)
        store = StorageManager(backend=StorageBackend.SQLITE)
        assert store.schema is None

    def test_invalid_env_backend_raises(self, monkeypatch):
        monkeypatch.setenv("LLMCYCLE_STORAGE_BACKEND", "baddb")
        with pytest.raises(ValueError, match="Unknown LLMCYCLE_STORAGE_BACKEND"):
            StorageManager()

    def test_custom_prefix_stored(self):
        store = StorageManager(backend=StorageBackend.SQLITE, table_prefix="myapp_")
        assert store.table_prefix == "myapp_"

    def test_custom_schema_stored(self):
        store = StorageManager(backend=StorageBackend.SQLITE, schema="analytics")
        assert store.schema == "analytics"


# ─── Ping ─────────────────────────────────────────────────────────────────────

class TestPing:
    async def test_ping_connected(self, store):
        result = await store.ping()
        assert result["ok"] is True
        assert result["backend"] == "sqlite"
        assert result["latency_ms"] >= 0

    async def test_ping_returns_url(self, store):
        result = await store.ping()
        assert "url" in result

    async def test_ping_before_connect(self):
        store = StorageManager(
            backend=StorageBackend.SQLITE,
            url="sqlite+aiosqlite:///:memory:",
        )
        result = await store.ping()
        assert result["ok"] is True

    async def test_ping_bad_url_returns_dict(self):
        store = StorageManager(
            backend=StorageBackend.SQLITE,
            url="sqlite+aiosqlite:///Z:/nonexistent/path/db.sqlite",
        )
        result = await store.ping()
        assert "ok" in result
        assert "backend" in result

    async def test_ping_latency_is_float(self, store):
        result = await store.ping()
        assert isinstance(result["latency_ms"], float)


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
        assert await store.get_workplace("nonexistent-id") is None

    async def test_list_workplaces(self, store):
        await store.create_workplace(Workplace(name="Alpha"))
        await store.create_workplace(Workplace(name="Beta"))
        wps = await store.list_workplaces()
        assert len(wps) == 2
        names = {w.name for w in wps}
        assert "Alpha" in names and "Beta" in names

    async def test_list_empty(self, store):
        assert await store.list_workplaces() == []

    async def test_workplace_metadata_round_trip(self, store):
        wp = Workplace(name="Meta", metadata={"tier": "enterprise", "region": "us-east"})
        await store.create_workplace(wp)
        fetched = await store.get_workplace(wp.id)
        assert fetched.metadata["tier"] == "enterprise"
        assert fetched.metadata["region"] == "us-east"


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

    async def test_get_nonexistent_returns_none(self, store):
        assert await store.get_team("nonexistent") is None

    async def test_list_teams_by_workplace(self, store):
        wp = Workplace(name="Org")
        await store.create_workplace(wp)
        await store.create_team(Team(name="Eng",   workplace_id=wp.id))
        await store.create_team(Team(name="Sales",  workplace_id=wp.id))
        await store.create_team(Team(name="Other",  workplace_id="other-wp"))
        teams = await store.list_teams(workplace_id=wp.id)
        assert len(teams) == 2
        assert all(t.workplace_id == wp.id for t in teams)

    async def test_list_teams_no_filter(self, store):
        await store.create_team(Team(name="A", workplace_id="wp1"))
        await store.create_team(Team(name="B", workplace_id="wp2"))
        all_teams = await store.list_teams()
        assert len(all_teams) == 2

    async def test_member_ids_preserved(self, store):
        team = Team(name="Dev", workplace_id="wp1", member_ids=["a", "b", "c"])
        await store.create_team(team)
        fetched = await store.get_team(team.id)
        assert fetched.member_ids == ["a", "b", "c"]


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
        assert (await store.get_user(user.id)).role == "member"
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

    async def test_user_email_optional(self, store):
        user = User(username="noemail")
        await store.create_user(user)
        fetched = await store.get_user(user.id)
        assert fetched.email is None

    async def test_user_roles(self, store):
        for role in ["admin", "member", "viewer"]:
            u = User(username=f"user_{role}", role=role)
            await store.create_user(u)
            fetched = await store.get_user(u.id)
            assert fetched.role == role


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
        assert updated.ended_at is not None

    async def test_list_sessions_by_user(self, store):
        for i in range(3):
            await store.create_session(Session(user_id="u3", model=f"model-{i}"))
        await store.create_session(Session(user_id="other", model="x"))
        sessions = await store.list_sessions(user_id="u3")
        assert len(sessions) == 3

    async def test_list_sessions_by_team(self, store):
        for _ in range(2):
            await store.create_session(Session(team_id="team-abc", model="gpt-4o"))
        sessions = await store.list_sessions(team_id="team-abc")
        assert len(sessions) == 2

    async def test_get_nonexistent_session(self, store):
        assert await store.get_session("no-such-id") is None

    async def test_session_limit(self, store):
        for i in range(10):
            await store.create_session(Session(user_id="u-lim", model="m"))
        sessions = await store.list_sessions(user_id="u-lim", limit=3)
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

    async def test_total_tokens_auto_computed(self, store):
        req = LLMRequest(model="m", provider="p", prompt_tokens=100, completion_tokens=50)
        assert req.total_tokens == 150

    async def test_total_tokens_explicit(self, store):
        req = LLMRequest(model="m", provider="p",
                         prompt_tokens=100, completion_tokens=50, total_tokens=999)
        # When explicitly set, use it
        assert req.total_tokens == 999

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

    async def test_get_nonexistent_request(self, store):
        assert await store.get_request("no-such-id") is None

    async def test_request_with_tags(self, store):
        req = LLMRequest(model="m", provider="p", tags=["prod", "chatbot"])
        await store.save_request(req)
        fetched = await store.get_request(req.id)
        assert "prod" in fetched.tags
        assert "chatbot" in fetched.tags

    async def test_request_with_cost(self, store):
        req = LLMRequest(model="gpt-4o", provider="openai", cost_usd=0.0042)
        await store.save_request(req)
        fetched = await store.get_request(req.id)
        assert abs(fetched.cost_usd - 0.0042) < 0.0001

    async def test_request_with_team_and_workplace(self, store):
        req = LLMRequest(model="m", provider="p",
                         team_id="team-1", workplace_id="wp-1")
        await store.save_request(req)
        fetched = await store.get_request(req.id)
        assert fetched.team_id == "team-1"
        assert fetched.workplace_id == "wp-1"

    async def test_request_fallback_used(self, store):
        req = LLMRequest(model="m", provider="p", fallback_used=True, retries=2)
        await store.save_request(req)
        fetched = await store.get_request(req.id)
        assert fetched.fallback_used is True
        assert fetched.retries == 2

    async def test_request_status_error(self, store):
        req = LLMRequest(model="m", provider="p",
                         status="error", error="Rate limit exceeded")
        await store.save_request(req)
        fetched = await store.get_request(req.id)
        assert fetched.status == "error"
        assert fetched.error == "Rate limit exceeded"


# ─── Request Lifecycle — cancel / timeout / update_status ─────────────────────

class TestRequestLifecycle:
    async def test_update_status_to_cancelled(self, store):
        req = LLMRequest(model="gpt-4o", provider="openai", status="success")
        await store.save_request(req)
        ts = time.time()
        await store.update_request_status(
            req.id, status="cancelled", cancelled_at=ts, error="Cancelled by user"
        )
        fetched = await store.get_request(req.id)
        assert fetched.status == "cancelled"
        assert fetched.error == "Cancelled by user"
        assert fetched.cancelled_at is not None
        assert abs(fetched.cancelled_at - ts) < 1.0

    async def test_update_status_to_timeout(self, store):
        req = LLMRequest(model="gpt-4o", provider="openai", status="success")
        await store.save_request(req)
        await store.update_request_status(
            req.id, status="timeout", error="Exceeded 30s timeout"
        )
        fetched = await store.get_request(req.id)
        assert fetched.status == "timeout"
        assert "30s" in fetched.error

    async def test_cancel_request_shortcut(self, store):
        req = LLMRequest(model="m", provider="p", status="success")
        await store.save_request(req)
        before = time.time()
        await store.cancel_request(req.id)
        after = time.time()
        fetched = await store.get_request(req.id)
        assert fetched.status == "cancelled"
        assert before <= fetched.cancelled_at <= after + 1

    async def test_update_status_error_field(self, store):
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        await store.update_request_status(req.id, status="error", error="Auth failed")
        fetched = await store.get_request(req.id)
        assert fetched.status == "error"
        assert fetched.error == "Auth failed"

    async def test_cancelled_requests_have_cancelled_at(self, store):
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        await store.cancel_request(req.id)
        fetched = await store.get_request(req.id)
        assert fetched.cancelled_at is not None

    async def test_update_nonexistent_request_no_crash(self, store):
        # Should not raise — just update 0 rows
        await store.update_request_status("nonexistent-id", status="cancelled")


# ─── Tool Calls ───────────────────────────────────────────────────────────────

class TestToolCalls:
    async def test_save_and_list(self, store):
        req = LLMRequest(model="gpt-4o", provider="openai", has_tool_calls=True)
        await store.save_request(req)
        tc = ToolCall(
            request_id=req.id,
            name="get_weather",
            arguments={"city": "London", "unit": "celsius"},
            arguments_raw='{"city": "London", "unit": "celsius"}',
        )
        saved = await store.save_tool_call(tc)
        assert saved.id == tc.id

        tools = await store.list_tool_calls(request_id=req.id)
        assert len(tools) == 1
        assert tools[0].name == "get_weather"
        assert tools[0].arguments["city"] == "London"

    async def test_update_tool_call_result(self, store):
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        tc = ToolCall(request_id=req.id, name="search", arguments={"q": "RAG"})
        await store.save_tool_call(tc)

        tc.result = '{"results": ["doc1", "doc2"]}'
        tc.executed_at = time.time()
        tc.status = "success"
        await store.update_tool_call(tc)

        tools = await store.list_tool_calls(request_id=req.id)
        assert tools[0].status == "success"
        assert "doc1" in tools[0].result
        assert tools[0].executed_at is not None

    async def test_tool_call_error_status(self, store):
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        tc = ToolCall(request_id=req.id, name="broken_tool", arguments={})
        await store.save_tool_call(tc)
        tc.status = "error"
        tc.error = "Tool execution failed"
        await store.update_tool_call(tc)
        tools = await store.list_tool_calls(request_id=req.id)
        assert tools[0].status == "error"
        assert tools[0].error == "Tool execution failed"

    async def test_list_tool_calls_by_status(self, store):
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        tc1 = ToolCall(request_id=req.id, name="fn1", arguments={})
        tc2 = ToolCall(request_id=req.id, name="fn2", arguments={})
        await store.save_tool_call(tc1)
        await store.save_tool_call(tc2)
        # Update one to success
        tc1.status = "success"
        await store.update_tool_call(tc1)

        pending = await store.list_tool_calls(request_id=req.id, status="pending")
        success = await store.list_tool_calls(request_id=req.id, status="success")
        assert len(pending) == 1
        assert len(success) == 1

    async def test_list_tool_calls_by_session(self, store):
        sid = "sess-tools"
        req = LLMRequest(model="m", provider="p", session_id=sid)
        await store.save_request(req)
        for i in range(3):
            await store.save_tool_call(ToolCall(
                request_id=req.id, session_id=sid,
                name=f"tool_{i}", arguments={},
            ))
        tools = await store.list_tool_calls(session_id=sid)
        assert len(tools) == 3

    async def test_multiple_tool_calls_per_request(self, store):
        req = LLMRequest(model="m", provider="p", has_tool_calls=True)
        await store.save_request(req)
        for name in ["search", "calculate", "send_email"]:
            await store.save_tool_call(ToolCall(
                request_id=req.id, name=name, arguments={"a": 1}
            ))
        tools = await store.list_tool_calls(request_id=req.id)
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert names == {"search", "calculate", "send_email"}

    async def test_tool_call_default_status_is_pending(self, store):
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        tc = ToolCall(request_id=req.id, name="fn", arguments={})
        await store.save_tool_call(tc)
        tools = await store.list_tool_calls(request_id=req.id)
        assert tools[0].status == "pending"

    async def test_list_tool_calls_empty(self, store):
        tools = await store.list_tool_calls(request_id="nonexistent")
        assert tools == []


# ─── Feedback ─────────────────────────────────────────────────────────────────

class TestFeedback:
    async def test_save_thumbs_up(self, store):
        req = LLMRequest(model="gpt-4o", provider="openai")
        await store.save_request(req)
        fb = RequestFeedback(
            request_id=req.id,
            user_id="u1",
            thumbs_up=True,
            rating=5,
            comment="Perfect!",
        )
        saved = await store.save_feedback(fb)
        assert saved.id == fb.id
        results = await store.list_feedback(request_id=req.id)
        assert len(results) == 1
        assert results[0].thumbs_up is True
        assert results[0].rating == 5
        assert results[0].comment == "Perfect!"

    async def test_save_thumbs_down(self, store):
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        fb = RequestFeedback(
            request_id=req.id,
            thumbs_up=False,
            rating=1,
            comment="Wrong answer",
            tags=["hallucination"],
        )
        await store.save_feedback(fb)
        results = await store.list_feedback(request_id=req.id)
        assert results[0].thumbs_up is False
        assert results[0].rating == 1
        assert "hallucination" in results[0].tags

    async def test_feedback_no_vote(self, store):
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        fb = RequestFeedback(request_id=req.id, comment="Neutral comment")
        await store.save_feedback(fb)
        results = await store.list_feedback(request_id=req.id)
        assert results[0].thumbs_up is None
        assert results[0].rating is None

    async def test_list_feedback_by_user(self, store):
        for i in range(3):
            req = LLMRequest(model="m", provider="p")
            await store.save_request(req)
            await store.save_feedback(RequestFeedback(
                request_id=req.id, user_id="user-feedback"
            ))
        results = await store.list_feedback(user_id="user-feedback")
        assert len(results) == 3

    async def test_list_feedback_by_session(self, store):
        sid = "sess-fb"
        for _ in range(2):
            req = LLMRequest(model="m", provider="p", session_id=sid)
            await store.save_request(req)
            await store.save_feedback(RequestFeedback(
                request_id=req.id, session_id=sid
            ))
        results = await store.list_feedback(session_id=sid)
        assert len(results) == 2

    async def test_feedback_tags_preserved(self, store):
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        fb = RequestFeedback(
            request_id=req.id,
            tags=["too_long", "off_topic", "hallucination"]
        )
        await store.save_feedback(fb)
        results = await store.list_feedback(request_id=req.id)
        assert set(results[0].tags) == {"too_long", "off_topic", "hallucination"}

    async def test_multiple_feedback_per_request(self, store):
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        await store.save_feedback(RequestFeedback(request_id=req.id, user_id="u1", rating=4))
        await store.save_feedback(RequestFeedback(request_id=req.id, user_id="u2", rating=2))
        results = await store.list_feedback(request_id=req.id)
        assert len(results) == 2
        ratings = {r.rating for r in results}
        assert ratings == {4, 2}

    async def test_list_feedback_empty(self, store):
        assert await store.list_feedback(request_id="nonexistent") == []


# ─── History ──────────────────────────────────────────────────────────────────

class TestHistory:
    async def test_append_and_get(self, store):
        sid = "sess-hist"
        await store.add_message(HistoryMessage(session_id=sid, role="user",      content="Hello"))
        await store.add_message(HistoryMessage(session_id=sid, role="assistant", content="Hi!"))
        history = await store.get_history(sid)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    async def test_clear_history(self, store):
        sid = "sess-clear"
        await store.add_message(HistoryMessage(session_id=sid, role="user", content="Bye"))
        await store.clear_history(sid)
        assert await store.get_history(sid) == []

    async def test_history_limit(self, store):
        sid = "sess-limit"
        for i in range(20):
            await store.add_message(HistoryMessage(session_id=sid, role="user", content=f"msg {i}"))
        history = await store.get_history(sid, limit=5)
        assert len(history) == 5

    async def test_history_roles(self, store):
        sid = "sess-roles"
        for role in ["system", "user", "assistant", "tool"]:
            await store.add_message(HistoryMessage(session_id=sid, role=role, content="x"))
        history = await store.get_history(sid)
        roles = {h.role for h in history}
        assert roles == {"system", "user", "assistant", "tool"}

    async def test_history_with_tool_call_id(self, store):
        sid = "sess-tool-hist"
        msg = HistoryMessage(
            session_id=sid,
            role="tool",
            content='{"result": "ok"}',
            tool_call_id="tc-123",
        )
        await store.add_message(msg)
        history = await store.get_history(sid)
        assert history[0].tool_call_id == "tc-123"

    async def test_history_with_request_id(self, store):
        sid = "sess-req-link"
        req = LLMRequest(model="m", provider="p")
        await store.save_request(req)
        await store.add_message(HistoryMessage(
            session_id=sid, role="assistant",
            content="Answer", request_id=req.id,
        ))
        history = await store.get_history(sid)
        assert history[0].request_id == req.id

    async def test_history_empty(self, store):
        assert await store.get_history("nonexistent-session") == []

    async def test_history_multiple_sessions_isolated(self, store):
        await store.add_message(HistoryMessage(session_id="s1", role="user", content="s1 msg"))
        await store.add_message(HistoryMessage(session_id="s2", role="user", content="s2 msg"))
        s1 = await store.get_history("s1")
        s2 = await store.get_history("s2")
        assert len(s1) == 1 and len(s2) == 1
        assert s1[0].content == "s1 msg"
        assert s2[0].content == "s2 msg"


# ─── Purge by range ───────────────────────────────────────────────────────────

class TestPurgeByRange:
    async def _seed(self, store, n=10):
        base = time.time() - n * 100
        reqs = []
        for i in range(n):
            r = LLMRequest.model_construct(**{
                "id": __import__("uuid").uuid4().__str__(),
                "model": "gpt-4o", "provider": "openai",
                "prompt": f"Q{i}", "response": "", "status": "success",
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                "latency_ms": 0.0, "fallback_used": False, "retries": 0,
                "tags": [], "has_tool_calls": False,
                "created_at": base + i * 100,
                "metadata": {},
            })
            await store.save_request(r)
            reqs.append(r)
        return reqs, base

    async def test_purge_requests_to_ts(self, store):
        reqs, base = await self._seed(store, 10)
        cutoff = base + 500
        result = await store.purge_by_range(to_ts=cutoff)
        assert result["deleted"]["requests"] >= 5
        remaining = await store.list_requests(limit=100)
        assert all(r.created_at > cutoff for r in remaining)

    async def test_purge_requests_from_ts(self, store):
        reqs, base = await self._seed(store, 10)
        cutoff = base + 500
        result = await store.purge_by_range(from_ts=cutoff)
        assert result["deleted"]["requests"] >= 4

    async def test_purge_requests_range(self, store):
        reqs, base = await self._seed(store, 10)
        result = await store.purge_by_range(from_ts=base + 100, to_ts=base + 500)
        assert result["deleted"]["requests"] >= 4

    async def test_purge_all_entities(self, store):
        reqs, base = await self._seed(store, 5)
        await store.create_session(Session(user_id="u", model="m", started_at=base + 50))
        await store.add_message(HistoryMessage(
            session_id="sid", role="user", content="x", created_at=base + 50
        ))
        result = await store.purge_by_range(to_ts=base + 300, entities=["all"])
        assert "requests" in result["deleted"]
        assert "history" in result["deleted"]
        assert "sessions" in result["deleted"]

    async def test_purge_no_range_deletes_all_requests(self, store):
        await self._seed(store, 3)
        result = await store.purge_by_range()
        assert result["deleted"]["requests"] == 3

    async def test_purge_sessions_only(self, store):
        for _ in range(3):
            await store.create_session(Session(user_id="u", model="m"))
        result = await store.purge_by_range(entities=["sessions"])
        assert result["deleted"]["sessions"] == 3
        assert "requests" not in result["deleted"]

    async def test_purge_returns_correct_counts(self, store):
        reqs, base = await self._seed(store, 5)
        result = await store.purge_by_range(to_ts=base + 250, entities=["requests"])
        # Should delete 3 (indices 0, 1, 2 → created_at = base+0, base+100, base+200)
        assert result["deleted"]["requests"] == 3

    async def test_purge_empty_store_no_crash(self, store):
        result = await store.purge_by_range(entities=["all"])
        assert result["deleted"]["requests"] == 0


# ─── Analytics ────────────────────────────────────────────────────────────────

class TestAnalytics:
    async def _seed(self, store):
        data = [
            dict(model="gpt-4o",        provider="openai",   prompt_tokens=100, completion_tokens=50,  latency_ms=300, status="success",   user_id="u1"),
            dict(model="gpt-4o",        provider="openai",   prompt_tokens=200, completion_tokens=80,  latency_ms=450, status="success",   user_id="u1"),
            dict(model="llama-3-70b",   provider="groq",     prompt_tokens=80,  completion_tokens=40,  latency_ms=90,  status="success",   user_id="u2"),
            dict(model="llama-3-70b",   provider="groq",     prompt_tokens=60,  completion_tokens=30,  latency_ms=80,  status="error",     user_id="u2"),
            dict(model="deepseek-chat", provider="deepseek", prompt_tokens=150, completion_tokens=70,  latency_ms=600, status="success",   user_id="u1", fallback_used=True),
        ]
        for d in data:
            await store.save_request(LLMRequest(**d))

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
        assert s["total_requests"] == 3

    async def test_summary_empty(self, store):
        s = await store.analytics.summary()
        assert s["total_requests"] == 0

    async def test_summary_fallback_rate(self, store):
        await self._seed(store)
        s = await store.analytics.summary()
        assert round(s["fallback_rate"], 2) == 0.2

    async def test_by_provider(self, store):
        await self._seed(store)
        bp = await store.analytics.by_provider()
        providers = [p["provider"] for p in bp]
        assert "openai" in providers and "groq" in providers and "deepseek" in providers
        openai = next(p for p in bp if p["provider"] == "openai")
        assert openai["requests"] == 2
        assert openai["tokens"] == 430  # (100+50)+(200+80)

    async def test_by_provider_errors(self, store):
        await self._seed(store)
        bp = await store.analytics.by_provider()
        groq = next(p for p in bp if p["provider"] == "groq")
        assert groq["errors"] == 1

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
        for _ in range(2):
            await store.save_request(LLMRequest(model="gpt-4o", provider="openai", session_id=sid))
        bs = await store.analytics.by_session()
        assert any(s["session_id"] == sid and s["requests"] == 2 for s in bs)

    async def test_timeseries_hour(self, store):
        await self._seed(store)
        ts = await store.analytics.timeseries(bucket="hour")
        assert isinstance(ts, list)
        assert sum(b["requests"] for b in ts) == 5

    async def test_timeseries_day(self, store):
        await self._seed(store)
        ts = await store.analytics.timeseries(bucket="day")
        assert isinstance(ts, list)

    async def test_timeseries_minute(self, store):
        await self._seed(store)
        ts = await store.analytics.timeseries(bucket="minute")
        assert isinstance(ts, list)

    async def test_top_errors(self, store):
        await store.save_request(LLMRequest(model="m", provider="p", status="error", error="Rate limited"))
        await store.save_request(LLMRequest(model="m", provider="p", status="error", error="Rate limited"))
        await store.save_request(LLMRequest(model="m", provider="p", status="error", error="Auth failed"))
        errors = await store.analytics.top_errors(limit=5)
        assert len(errors) >= 1
        assert errors[0]["error"] == "Rate limited"
        assert errors[0]["count"] == 2

    async def test_summary_with_time_range(self, store):
        await self._seed(store)
        now = time.time()
        s = await store.analytics.summary(from_ts=now - 86400, to_ts=now + 60)
        assert s["total_requests"] == 5

    async def test_summary_excludes_outside_range(self, store):
        await self._seed(store)
        far_future = time.time() + 86400
        s = await store.analytics.summary(from_ts=far_future)
        assert s["total_requests"] == 0

    async def test_by_provider_sorted_by_request_count(self, store):
        await self._seed(store)
        bp = await store.analytics.by_provider()
        counts = [p["requests"] for p in bp]
        assert counts == sorted(counts, reverse=True)

    async def test_analytics_latency_stats(self, store):
        await self._seed(store)
        s = await store.analytics.summary()
        latencies = [300, 450, 90, 80, 600]
        expected_avg = sum(latencies) / len(latencies)
        assert abs(s["avg_latency_ms"] - expected_avg) < 1.0
