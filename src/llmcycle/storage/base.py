"""
LLMCycle Storage — Abstract Base + Backend Enum
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List

from llmcycle.storage.models import (
    Workplace, Team, User, Session, LLMRequest, HistoryMessage
)


class StorageBackend(Enum):
    """
    Choose exactly ONE backend.

    Usage:
        from llmcycle.storage import StorageBackend, StorageManager

        store = StorageManager(
            backend=StorageBackend.SQLITE,
            url="sqlite+aiosqlite:///./llmcycle.db"
        )

        # or
        store = StorageManager(StorageBackend.POSTGRES,  "postgresql+asyncpg://user:pass@host/db")
        store = StorageManager(StorageBackend.MYSQL,     "mysql+aiomysql://user:pass@host/db")
        store = StorageManager(StorageBackend.MSSQL,     "mssql+aioodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server")
        store = StorageManager(StorageBackend.MONGO,     "mongodb://localhost:27017/llmcycle")
        store = StorageManager(StorageBackend.REDIS,     "redis://localhost:6379/0")
    """
    SQLITE   = "sqlite"
    POSTGRES = "postgres"
    MYSQL    = "mysql"
    MSSQL    = "mssql"
    MONGO    = "mongo"
    REDIS    = "redis"


class BaseStorage(ABC):
    """Abstract interface every backend must implement."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def ping(self) -> dict:
        """
        Test the connection. Returns:
            {"ok": True, "backend": "sqlite", "latency_ms": 1.2}
        or:
            {"ok": False, "backend": "redis", "error": "Connection refused"}
        """
        ...

    # ── Workplaces ──────────────────────────────────────────────────
    @abstractmethod
    async def create_workplace(self, wp: Workplace) -> Workplace: ...

    @abstractmethod
    async def get_workplace(self, id: str) -> Optional[Workplace]: ...

    @abstractmethod
    async def list_workplaces(self) -> List[Workplace]: ...

    # ── Teams ────────────────────────────────────────────────────────
    @abstractmethod
    async def create_team(self, team: Team) -> Team: ...

    @abstractmethod
    async def get_team(self, id: str) -> Optional[Team]: ...

    @abstractmethod
    async def list_teams(self, workplace_id: Optional[str] = None) -> List[Team]: ...

    # ── Users ────────────────────────────────────────────────────────
    @abstractmethod
    async def create_user(self, user: User) -> User: ...

    @abstractmethod
    async def get_user(self, id: str) -> Optional[User]: ...

    @abstractmethod
    async def get_user_by_username(self, username: str) -> Optional[User]: ...

    @abstractmethod
    async def list_users(self, team_id: Optional[str] = None) -> List[User]: ...

    @abstractmethod
    async def update_user(self, user: User) -> User: ...

    @abstractmethod
    async def delete_user(self, id: str) -> None: ...

    # ── Sessions ─────────────────────────────────────────────────────
    @abstractmethod
    async def create_session(self, session: Session) -> Session: ...

    @abstractmethod
    async def get_session(self, id: str) -> Optional[Session]: ...

    @abstractmethod
    async def update_session(self, session: Session) -> Session: ...

    @abstractmethod
    async def list_sessions(self, user_id: Optional[str] = None,
                            team_id: Optional[str] = None,
                            limit: int = 50) -> List[Session]: ...

    # ── Requests ─────────────────────────────────────────────────────
    @abstractmethod
    async def save_request(self, req: LLMRequest) -> LLMRequest: ...

    @abstractmethod
    async def get_request(self, id: str) -> Optional[LLMRequest]: ...

    @abstractmethod
    async def list_requests(self, session_id: Optional[str] = None,
                            user_id: Optional[str] = None,
                            limit: int = 100) -> List[LLMRequest]: ...

    # ── History ──────────────────────────────────────────────────────
    @abstractmethod
    async def append_history(self, msg: HistoryMessage) -> HistoryMessage: ...

    @abstractmethod
    async def get_history(self, session_id: str,
                          limit: int = 100) -> List[HistoryMessage]: ...

    @abstractmethod
    async def clear_history(self, session_id: str) -> None: ...

    @abstractmethod
    async def purge_by_range(
        self,
        from_ts: Optional[float] = None,
        to_ts: Optional[float] = None,
        entities: Optional[List[str]] = None,
    ) -> dict:
        """
        Delete stored data by date range.

        Args:
            from_ts:  Unix timestamp lower bound (inclusive). None = no lower bound.
            to_ts:    Unix timestamp upper bound (inclusive). None = no upper bound.
            entities: Which entity types to purge. Options:
                        "requests"  - LLM request logs
                        "history"   - Conversation history messages
                        "sessions"  - Session records
                        "all"       - Everything above
                      Default: ["requests"] (safest)

        Returns:
            {"deleted": {"requests": 120, "history": 340, "sessions": 15}}

        Examples::

            # Delete all requests older than 30 days
            import time
            await store.purge_by_range(to_ts=time.time() - 30 * 86400)

            # Delete everything in a specific range
            await store.purge_by_range(
                from_ts=1700000000,
                to_ts=1700086400,
                entities=["requests", "history", "sessions"]
            )

            # Delete all cached data (full wipe)
            await store.purge_by_range(entities=["all"])
        """
        ...
