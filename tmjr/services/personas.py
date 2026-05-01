"""Lógica de dominio sobre personas / DM / PJ."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db.models import DM, PJ, Persona


async def get_or_create_persona(
    session: AsyncSession,
    *,
    telegram_id: int,
    nombre: str,
) -> tuple[Persona, bool]:
    """Devuelve (persona, created). Idempotente por telegram_id."""
    result = await session.execute(select(Persona).where(Persona.telegram_id == telegram_id))
    persona = result.scalar_one_or_none()
    if persona is not None:
        return persona, False

    persona = Persona(telegram_id=telegram_id, nombre=nombre)
    session.add(persona)
    await session.commit()
    await session.refresh(persona)
    return persona, True


async def get_persona_by_telegram(session: AsyncSession, telegram_id: int) -> Persona | None:
    result = await session.execute(select(Persona).where(Persona.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_persona(session: AsyncSession, persona_id: int) -> Persona | None:
    return await session.get(Persona, persona_id)


async def ensure_dm(
    session: AsyncSession,
    persona: Persona,
    *,
    biografia: str | None = None,
) -> DM:
    """Si la persona no tiene perfil DM, lo crea y lo enlaza. Devuelve el DM."""
    if persona.id_master is not None:
        dm = await session.get(DM, persona.id_master)
        if dm is not None:
            return dm

    dm = DM(biografia=biografia)
    session.add(dm)
    await session.flush()  # asigna dm.id
    persona.id_master = dm.id
    await session.commit()
    await session.refresh(persona)
    await session.refresh(dm)
    return dm


async def ensure_pj(
    session: AsyncSession,
    persona: Persona,
    *,
    nombre: str,
    descripcion: str | None = None,
) -> PJ:
    """Si la persona no tiene perfil PJ, lo crea y lo enlaza. Devuelve el PJ."""
    if persona.id_pj is not None:
        pj = await session.get(PJ, persona.id_pj)
        if pj is not None:
            return pj

    pj = PJ(nombre=nombre, descripcion=descripcion)
    session.add(pj)
    await session.flush()
    persona.id_pj = pj.id
    await session.commit()
    await session.refresh(persona)
    await session.refresh(pj)
    return pj
