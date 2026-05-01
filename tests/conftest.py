"""Fixtures compartidas para los tests unitarios.

- Engine SQLite en memoria (rápido, sin necesidad de Postgres).
- `session` por test con rollback al final → aislamiento total.
- `client` httpx contra la app FastAPI con `get_session` sobreescrito,
  sin disparar el lifespan (no se construye el bot, no hace falta TELEGRAM_TOKEN).
"""
from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tmjr.db import get_session
from tmjr.db import models  # noqa: F401  - registra los modelos en Base.metadata
from tmjr.db.session import Base
from tmjr.main import app


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:  # type: ignore[override]
    sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with sm() as s:
        yield s


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncClient:  # type: ignore[override]
    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
    app.dependency_overrides.clear()
