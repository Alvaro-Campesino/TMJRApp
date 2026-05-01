"""Engine y sessionmaker async, resueltos perezosamente.

La inicialización tardía permite a los tests cambiar `DATABASE_URL` y
llamar a `reset_db_state()` para reciclar las conexiones contra la DB
de test antes de que los handlers del bot las usen.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from tmjr.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, future=True, echo=False)
    return _engine


def _get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_maker


class _LazySessionMaker:
    """Proxy callable: `async_session_maker()` -> AsyncSession context manager.

    Usado por los handlers del bot:
        async with async_session_maker() as session: ...
    """

    def __call__(self) -> AsyncSession:
        return _get_session_maker()()


async_session_maker = _LazySessionMaker()


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependencia FastAPI para obtener una sesión por request."""
    async with _get_session_maker()() as session:
        yield session


async def reset_db_state() -> None:
    """Test-only: cierra el engine actual y limpia las cachés.

    Tras llamar esto, la siguiente operación recreará el engine usando
    los settings actuales (útil tras cambiar DATABASE_URL en tests).
    """
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_maker = None
