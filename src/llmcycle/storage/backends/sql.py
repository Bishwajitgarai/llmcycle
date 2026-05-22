"""
SQLAlchemy async backend — covers SQLite, PostgreSQL, MySQL, MSSQL.
One implementation, four databases.

Required packages per DB:
  SQLite:   pip install aiosqlite
  Postgres: pip install asyncpg
  MySQL:    pip install aiomysql
  MSSQL:    pip install aioodbc
"""
from __future__ import annotations
import json
from typing import Optional, List, Any

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Text, Float, Integer, Boolean, select, delete

from llmcycle.storage.base import BaseStorage
from llmcycle.storage.models import (
    Workplace, Team, User, Session, LLMRequest, HistoryMessage
)


# ─── ORM Tables ──────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass

def _j(v) -> str:  return json.dumps(v)
def _u(s) -> Any:  return json.loads(s) if s else {}
def _ul(s) -> Any: return json.loads(s) if s else []


class WorkplaceRow(Base):
    __tablename__ = "workplaces"
    id: Mapped[str]      = mapped_column(Text, primary_key=True)
    name: Mapped[str]    = mapped_column(Text)
    settings: Mapped[str]    = mapped_column(Text, default="{}")
    created_at: Mapped[float] = mapped_column(Float)
    metadata_: Mapped[str]   = mapped_column("metadata", Text, default="{}")

class TeamRow(Base):
    __tablename__ = "teams"
    id: Mapped[str]           = mapped_column(Text, primary_key=True)
    name: Mapped[str]         = mapped_column(Text)
    workplace_id: Mapped[str] = mapped_column(Text)
    member_ids: Mapped[str]   = mapped_column(Text, default="[]")
    created_at: Mapped[float] = mapped_column(Float)
    metadata_: Mapped[str]    = mapped_column("metadata", Text, default="{}")

class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str]             = mapped_column(Text, primary_key=True)
    username: Mapped[str]       = mapped_column(Text, unique=True, index=True)
    email: Mapped[Optional[str]]= mapped_column(Text, nullable=True)
    role: Mapped[str]           = mapped_column(Text, default="member")
    team_id: Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    workplace_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[float]   = mapped_column(Float)
    metadata_: Mapped[str]      = mapped_column("metadata", Text, default="{}")

class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[str]              = mapped_column(Text, primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    team_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[str]           = mapped_column(Text, default="")
    started_at: Mapped[float]    = mapped_column(Float)
    ended_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_requests: Mapped[int]  = mapped_column(Integer, default=0)
    total_tokens: Mapped[int]    = mapped_column(Integer, default=0)
    metadata_: Mapped[str]       = mapped_column("metadata", Text, default="{}")

class RequestRow(Base):
    __tablename__ = "llm_requests"
    id: Mapped[str]              = mapped_column(Text, primary_key=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    user_id: Mapped[Optional[str]]    = mapped_column(Text, nullable=True, index=True)
    model: Mapped[str]           = mapped_column(Text)
    provider: Mapped[str]        = mapped_column(Text)
    prompt: Mapped[str]          = mapped_column(Text, default="")
    response: Mapped[str]        = mapped_column(Text, default="")
    prompt_tokens: Mapped[int]   = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float]    = mapped_column(Float, default=0.0)
    status: Mapped[str]          = mapped_column(Text, default="success")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fallback_used: Mapped[bool]  = mapped_column(Boolean, default=False)
    retries: Mapped[int]         = mapped_column(Integer, default=0)
    created_at: Mapped[float]    = mapped_column(Float)
    metadata_: Mapped[str]       = mapped_column("metadata", Text, default="{}")

class HistoryRow(Base):
    __tablename__ = "history"
    id: Mapped[str]              = mapped_column(Text, primary_key=True)
    session_id: Mapped[str]      = mapped_column(Text, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[str]            = mapped_column(Text)
    content: Mapped[str]         = mapped_column(Text)
    created_at: Mapped[float]    = mapped_column(Float)
    metadata_: Mapped[str]       = mapped_column("metadata", Text, default="{}")


# ─── Backend ──────────────────────────────────────────────────────────────────

class SQLStorage(BaseStorage):
    """
    Single SQLAlchemy async backend for SQLite / PostgreSQL / MySQL / MSSQL.

    Args:
        url:          SQLAlchemy async connection URL.
        schema:       DB schema name (PostgreSQL/MSSQL). None = use DB default.
        table_prefix: Prefix for all table names. Default: "llmc_".

    URL format:
        sqlite:   sqlite+aiosqlite:///./llmcycle.db
        postgres: postgresql+asyncpg://user:pass@host/db
        mysql:    mysql+aiomysql://user:pass@host/db
        mssql:    mssql+aioodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server
    """

    def __init__(self, url: str, schema: Optional[str] = None, table_prefix: str = "llmc_"):
        self.url = url
        self.schema = schema
        self.table_prefix = table_prefix
        self._engine = None
        self._session_factory = None
        self._meta: Optional[Base] = None

    def _make_meta(self) -> Base:
        """Dynamically create ORM metadata with custom table names and schema."""
        p = self.table_prefix
        s = self.schema

        class _Base(DeclarativeBase):
            pass

        class _WorkplaceRow(_Base):
            __tablename__ = f"{p}workplaces"
            __table_args__ = ({"schema": s} if s else {})
            id: Mapped[str]       = mapped_column(Text, primary_key=True)
            name: Mapped[str]     = mapped_column(Text)
            settings: Mapped[str] = mapped_column(Text, default="{}")
            created_at: Mapped[float] = mapped_column(Float)
            metadata_: Mapped[str]    = mapped_column("metadata", Text, default="{}")

        class _TeamRow(_Base):
            __tablename__ = f"{p}teams"
            __table_args__ = ({"schema": s} if s else {})
            id: Mapped[str]           = mapped_column(Text, primary_key=True)
            name: Mapped[str]         = mapped_column(Text)
            workplace_id: Mapped[str] = mapped_column(Text)
            member_ids: Mapped[str]   = mapped_column(Text, default="[]")
            created_at: Mapped[float] = mapped_column(Float)
            metadata_: Mapped[str]    = mapped_column("metadata", Text, default="{}")

        class _UserRow(_Base):
            __tablename__ = f"{p}users"
            __table_args__ = ({"schema": s} if s else {})
            id: Mapped[str]                = mapped_column(Text, primary_key=True)
            username: Mapped[str]          = mapped_column(Text, unique=True, index=True)
            email: Mapped[Optional[str]]   = mapped_column(Text, nullable=True)
            role: Mapped[str]              = mapped_column(Text, default="member")
            team_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
            workplace_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
            hashed_password: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
            created_at: Mapped[float]      = mapped_column(Float)
            metadata_: Mapped[str]         = mapped_column("metadata", Text, default="{}")

        class _SessionRow(_Base):
            __tablename__ = f"{p}sessions"
            __table_args__ = ({"schema": s} if s else {})
            id: Mapped[str]                   = mapped_column(Text, primary_key=True)
            user_id: Mapped[Optional[str]]    = mapped_column(Text, nullable=True, index=True)
            team_id: Mapped[Optional[str]]    = mapped_column(Text, nullable=True)
            model: Mapped[str]                = mapped_column(Text, default="")
            started_at: Mapped[float]         = mapped_column(Float)
            ended_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
            total_requests: Mapped[int]       = mapped_column(Integer, default=0)
            total_tokens: Mapped[int]         = mapped_column(Integer, default=0)
            metadata_: Mapped[str]            = mapped_column("metadata", Text, default="{}")

        class _RequestRow(_Base):
            __tablename__ = f"{p}requests"
            __table_args__ = ({"schema": s} if s else {})
            id: Mapped[str]                   = mapped_column(Text, primary_key=True)
            session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
            user_id: Mapped[Optional[str]]    = mapped_column(Text, nullable=True, index=True)
            model: Mapped[str]                = mapped_column(Text)
            provider: Mapped[str]             = mapped_column(Text)
            prompt: Mapped[str]               = mapped_column(Text, default="")
            response: Mapped[str]             = mapped_column(Text, default="")
            prompt_tokens: Mapped[int]        = mapped_column(Integer, default=0)
            completion_tokens: Mapped[int]    = mapped_column(Integer, default=0)
            latency_ms: Mapped[float]         = mapped_column(Float, default=0.0)
            status: Mapped[str]               = mapped_column(Text, default="success")
            error: Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
            fallback_used: Mapped[bool]       = mapped_column(Boolean, default=False)
            retries: Mapped[int]              = mapped_column(Integer, default=0)
            created_at: Mapped[float]         = mapped_column(Float)
            metadata_: Mapped[str]            = mapped_column("metadata", Text, default="{}")

        class _HistoryRow(_Base):
            __tablename__ = f"{p}history"
            __table_args__ = ({"schema": s} if s else {})
            id: Mapped[str]                   = mapped_column(Text, primary_key=True)
            session_id: Mapped[str]           = mapped_column(Text, index=True)
            request_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
            role: Mapped[str]                 = mapped_column(Text)
            content: Mapped[str]              = mapped_column(Text)
            created_at: Mapped[float]         = mapped_column(Float)
            metadata_: Mapped[str]            = mapped_column("metadata", Text, default="{}")

        # Expose row classes as instance attributes for CRUD methods
        self.WorkplaceRow = _WorkplaceRow
        self.TeamRow      = _TeamRow
        self.UserRow      = _UserRow
        self.SessionRow   = _SessionRow
        self.RequestRow   = _RequestRow
        self.HistoryRow   = _HistoryRow
        return _Base

    async def connect(self):
        self._engine = create_async_engine(self.url, echo=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def disconnect(self):
        if self._engine:
            await self._engine.dispose()

    async def ping(self) -> dict:
        """Verify the DB connection with a lightweight SELECT 1."""
        import time
        backend_name = self.url.split(":")[0].split("+")[0]  # e.g. 'sqlite', 'postgresql'
        try:
            t0 = time.monotonic()
            from sqlalchemy import text
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            return {"ok": True, "backend": backend_name, "url": self.url, "latency_ms": latency_ms}
        except Exception as e:
            return {"ok": False, "backend": backend_name, "url": self.url, "error": str(e)}

    def _s(self) -> AsyncSession:
        return self._session_factory()

    # ── Workplaces ──────────────────────────────────────────────────
    async def create_workplace(self, wp: Workplace) -> Workplace:
        async with self._s() as s:
            s.add(WorkplaceRow(id=wp.id, name=wp.name, settings=_j(wp.settings), created_at=wp.created_at, metadata_=_j(wp.metadata)))
            await s.commit()
        return wp

    async def get_workplace(self, id: str) -> Optional[Workplace]:
        async with self._s() as s:
            row = await s.get(WorkplaceRow, id)
            return Workplace(id=row.id, name=row.name, settings=_u(row.settings), created_at=row.created_at, metadata=_u(row.metadata_)) if row else None

    async def list_workplaces(self) -> List[Workplace]:
        async with self._s() as s:
            rows = (await s.execute(select(WorkplaceRow))).scalars().all()
            return [Workplace(id=r.id, name=r.name, settings=_u(r.settings), created_at=r.created_at, metadata=_u(r.metadata_)) for r in rows]

    # ── Teams ────────────────────────────────────────────────────────
    async def create_team(self, team: Team) -> Team:
        async with self._s() as s:
            s.add(TeamRow(id=team.id, name=team.name, workplace_id=team.workplace_id, member_ids=_j(team.member_ids), created_at=team.created_at, metadata_=_j(team.metadata)))
            await s.commit()
        return team

    async def get_team(self, id: str) -> Optional[Team]:
        async with self._s() as s:
            row = await s.get(TeamRow, id)
            return Team(id=row.id, name=row.name, workplace_id=row.workplace_id, member_ids=_ul(row.member_ids), created_at=row.created_at, metadata=_u(row.metadata_)) if row else None

    async def list_teams(self, workplace_id: Optional[str] = None) -> List[Team]:
        async with self._s() as s:
            q = select(TeamRow)
            if workplace_id:
                q = q.where(TeamRow.workplace_id == workplace_id)
            rows = (await s.execute(q)).scalars().all()
            return [Team(id=r.id, name=r.name, workplace_id=r.workplace_id, member_ids=_ul(r.member_ids), created_at=r.created_at, metadata=_u(r.metadata_)) for r in rows]

    # ── Users ────────────────────────────────────────────────────────
    async def create_user(self, user: User) -> User:
        async with self._s() as s:
            s.add(UserRow(id=user.id, username=user.username, email=user.email, role=user.role, team_id=user.team_id, workplace_id=user.workplace_id, hashed_password=user.hashed_password, created_at=user.created_at, metadata_=_j(user.metadata)))
            await s.commit()
        return user

    async def get_user(self, id: str) -> Optional[User]:
        async with self._s() as s:
            row = await s.get(UserRow, id)
            return self._user(row) if row else None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        async with self._s() as s:
            row = (await s.execute(select(UserRow).where(UserRow.username == username))).scalar_one_or_none()
            return self._user(row) if row else None

    async def list_users(self, team_id: Optional[str] = None) -> List[User]:
        async with self._s() as s:
            q = select(UserRow)
            if team_id:
                q = q.where(UserRow.team_id == team_id)
            return [self._user(r) for r in (await s.execute(q)).scalars().all()]

    async def update_user(self, user: User) -> User:
        async with self._s() as s:
            row = await s.get(UserRow, user.id)
            if row:
                row.username = user.username; row.email = user.email; row.role = user.role
                row.team_id = user.team_id; row.workplace_id = user.workplace_id
                row.hashed_password = user.hashed_password; row.metadata_ = _j(user.metadata)
                await s.commit()
        return user

    async def delete_user(self, id: str) -> None:
        async with self._s() as s:
            await s.execute(delete(UserRow).where(UserRow.id == id))
            await s.commit()

    def _user(self, r: UserRow) -> User:
        return User(id=r.id, username=r.username, email=r.email, role=r.role, team_id=r.team_id, workplace_id=r.workplace_id, hashed_password=r.hashed_password, created_at=r.created_at, metadata=_u(r.metadata_))

    # ── Sessions ─────────────────────────────────────────────────────
    async def create_session(self, session: Session) -> Session:
        async with self._s() as s:
            s.add(SessionRow(id=session.id, user_id=session.user_id, team_id=session.team_id, model=session.model, started_at=session.started_at, ended_at=session.ended_at, total_requests=session.total_requests, total_tokens=session.total_tokens, metadata_=_j(session.metadata)))
            await s.commit()
        return session

    async def get_session(self, id: str) -> Optional[Session]:
        async with self._s() as s:
            row = await s.get(SessionRow, id)
            return self._session(row) if row else None

    async def update_session(self, session: Session) -> Session:
        async with self._s() as s:
            row = await s.get(SessionRow, session.id)
            if row:
                row.ended_at = session.ended_at; row.total_requests = session.total_requests
                row.total_tokens = session.total_tokens; row.metadata_ = _j(session.metadata)
                await s.commit()
        return session

    async def list_sessions(self, user_id=None, team_id=None, limit=50) -> List[Session]:
        async with self._s() as s:
            q = select(SessionRow)
            if user_id: q = q.where(SessionRow.user_id == user_id)
            if team_id: q = q.where(SessionRow.team_id == team_id)
            q = q.limit(limit).order_by(SessionRow.started_at.desc())
            return [self._session(r) for r in (await s.execute(q)).scalars().all()]

    def _session(self, r: SessionRow) -> Session:
        return Session(id=r.id, user_id=r.user_id, team_id=r.team_id, model=r.model, started_at=r.started_at, ended_at=r.ended_at, total_requests=r.total_requests, total_tokens=r.total_tokens, metadata=_u(r.metadata_))

    # ── Requests ─────────────────────────────────────────────────────
    async def save_request(self, req: LLMRequest) -> LLMRequest:
        async with self._s() as s:
            s.add(RequestRow(id=req.id, session_id=req.session_id, user_id=req.user_id, model=req.model, provider=req.provider, prompt=req.prompt, response=req.response, prompt_tokens=req.prompt_tokens, completion_tokens=req.completion_tokens, latency_ms=req.latency_ms, status=req.status, error=req.error, fallback_used=req.fallback_used, retries=req.retries, created_at=req.created_at, metadata_=_j(req.metadata)))
            await s.commit()
        return req

    async def get_request(self, id: str) -> Optional[LLMRequest]:
        async with self._s() as s:
            row = await s.get(RequestRow, id)
            return self._req(row) if row else None

    async def list_requests(self, session_id=None, user_id=None, limit=100) -> List[LLMRequest]:
        async with self._s() as s:
            q = select(RequestRow)
            if session_id: q = q.where(RequestRow.session_id == session_id)
            if user_id: q = q.where(RequestRow.user_id == user_id)
            q = q.limit(limit).order_by(RequestRow.created_at.desc())
            return [self._req(r) for r in (await s.execute(q)).scalars().all()]

    def _req(self, r: RequestRow) -> LLMRequest:
        return LLMRequest(id=r.id, session_id=r.session_id, user_id=r.user_id, model=r.model, provider=r.provider, prompt=r.prompt, response=r.response, prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens, latency_ms=r.latency_ms, status=r.status, error=r.error, fallback_used=r.fallback_used, retries=r.retries, created_at=r.created_at, metadata=_u(r.metadata_))

    # ── History ──────────────────────────────────────────────────────
    async def append_history(self, msg: HistoryMessage) -> HistoryMessage:
        async with self._s() as s:
            s.add(HistoryRow(id=msg.id, session_id=msg.session_id, request_id=msg.request_id, role=msg.role, content=msg.content, created_at=msg.created_at, metadata_=_j(msg.metadata)))
            await s.commit()
        return msg

    async def get_history(self, session_id: str, limit=100) -> List[HistoryMessage]:
        async with self._s() as s:
            q = select(HistoryRow).where(HistoryRow.session_id == session_id).order_by(HistoryRow.created_at).limit(limit)
            rows = (await s.execute(q)).scalars().all()
            return [HistoryMessage(id=r.id, session_id=r.session_id, request_id=r.request_id, role=r.role, content=r.content, created_at=r.created_at, metadata=_u(r.metadata_)) for r in rows]

    async def clear_history(self, session_id: str) -> None:
        async with self._s() as s:
            await s.execute(delete(HistoryRow).where(HistoryRow.session_id == session_id))
            await s.commit()

    # ── Purge by date range ───────────────────────────────────────────
    async def purge_by_range(
        self,
        from_ts: Optional[float] = None,
        to_ts: Optional[float] = None,
        entities: Optional[List[str]] = None,
    ) -> dict:
        """Delete rows within a timestamp range. Returns deleted count per entity."""
        targets = set(entities or ["requests"])
        if "all" in targets:
            targets = {"requests", "history", "sessions"}

        deleted = {}
        # Use dynamic row classes if _make_meta was called, else fall back to module-level
        RR = getattr(self, "RequestRow", RequestRow)
        HR = getattr(self, "HistoryRow", HistoryRow)
        SR = getattr(self, "SessionRow", SessionRow)

        def _range_clause(col):
            clauses = []
            if from_ts is not None: clauses.append(col >= from_ts)
            if to_ts   is not None: clauses.append(col <= to_ts)
            return clauses

        async with self._s() as s:
            if "requests" in targets:
                q = delete(RR)
                for c in _range_clause(RR.created_at): q = q.where(c)
                result = await s.execute(q)
                deleted["requests"] = result.rowcount

            if "history" in targets:
                q = delete(HR)
                for c in _range_clause(HR.created_at): q = q.where(c)
                result = await s.execute(q)
                deleted["history"] = result.rowcount

            if "sessions" in targets:
                q = delete(SR)
                for c in _range_clause(SR.started_at): q = q.where(c)
                result = await s.execute(q)
                deleted["sessions"] = result.rowcount

            await s.commit()

        return {"deleted": deleted}
