"""Helpers de lectura/escritura sobre la tabla `app_config` (key/value)."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db.models import AppConfig

# Claves conocidas.
PIN_MESSAGE_ID = "pin_message_id"


async def get(session: AsyncSession, key: str) -> str | None:
    row = (
        await session.execute(select(AppConfig).where(AppConfig.key == key))
    ).scalar_one_or_none()
    return row.value if row else None


async def set_(session: AsyncSession, key: str, value: str) -> None:
    """Upsert: si existe se actualiza, si no se crea."""
    row = (
        await session.execute(select(AppConfig).where(AppConfig.key == key))
    ).scalar_one_or_none()
    if row is None:
        session.add(AppConfig(key=key, value=value))
    else:
        row.value = value
    await session.commit()


async def delete_(session: AsyncSession, key: str) -> None:
    await session.execute(delete(AppConfig).where(AppConfig.key == key))
    await session.commit()
