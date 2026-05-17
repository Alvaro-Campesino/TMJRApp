"""Suscripciones de Persona a Premisa.

Modelo: una Persona puede suscribirse a N premisas. Cuando se publica
una sesión (no-campaña, o primera sesión de una campaña) con una premisa
suscrita, el publicador notifica a los suscriptores. Y al suscribirse,
se notifica a los DMs que han "usado" esa premisa (catálogo o sesión
publicada).
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db.models import (
    DMPremisa,
    Persona,
    Premisa,
    Sesion,
    SuscripcionPremisa,
)


async def is_subscribed(
    session: AsyncSession, persona_id: int, premisa_id: int
) -> SuscripcionPremisa | None:
    result = await session.execute(
        select(SuscripcionPremisa).where(
            SuscripcionPremisa.id_persona == persona_id,
            SuscripcionPremisa.id_premisa == premisa_id,
        )
    )
    return result.scalar_one_or_none()


async def subscribe(
    session: AsyncSession, *, persona_id: int, premisa_id: int
) -> tuple[SuscripcionPremisa, bool]:
    """Suscribe a la persona si no lo estaba ya. Idempotente.

    Devuelve (sub, created).
    """
    existing = await is_subscribed(session, persona_id, premisa_id)
    if existing is not None:
        return existing, False
    sub = SuscripcionPremisa(id_persona=persona_id, id_premisa=premisa_id)
    session.add(sub)
    await session.commit()
    await session.refresh(sub)
    return sub, True


async def unsubscribe(
    session: AsyncSession, *, persona_id: int, premisa_id: int
) -> bool:
    """Desuscribe. Devuelve True si había suscripción, False si no."""
    existing = await is_subscribed(session, persona_id, premisa_id)
    if existing is None:
        return False
    await session.delete(existing)
    await session.commit()
    return True


async def list_by_persona(
    session: AsyncSession, persona_id: int
) -> list[Premisa]:
    """Premisas a las que está suscrita la persona, orden alfabético."""
    result = await session.execute(
        select(Premisa)
        .join(SuscripcionPremisa, SuscripcionPremisa.id_premisa == Premisa.id)
        .where(SuscripcionPremisa.id_persona == persona_id)
        .order_by(Premisa.nombre)
    )
    return list(result.scalars().all())


async def list_suscriptores(
    session: AsyncSession, premisa_id: int
) -> list[Persona]:
    """Personas suscritas a esta premisa."""
    result = await session.execute(
        select(Persona)
        .join(SuscripcionPremisa, SuscripcionPremisa.id_persona == Persona.id)
        .where(SuscripcionPremisa.id_premisa == premisa_id)
    )
    return list(result.scalars().all())


async def dms_que_han_usado_premisa(
    session: AsyncSession, premisa_id: int
) -> list[int]:
    """IDs de DM que han "usado" la premisa.

    Definición de "usada": el DM tiene la premisa en su catálogo
    (`dm_premisas`) O ha publicado al menos una sesión con esa premisa.
    """
    catalogo = await session.execute(
        select(DMPremisa.id_dm).where(DMPremisa.id_premisa == premisa_id)
    )
    publicadas = await session.execute(
        select(Sesion.id_dm)
        .where(Sesion.id_premisa == premisa_id)
        .distinct()
    )
    return list(
        set(catalogo.scalars().all()) | set(publicadas.scalars().all())
    )


async def premisas_usadas_por_dm_con_suscriptores(
    session: AsyncSession, dm_id: int
) -> list[tuple[Premisa, int]]:
    """Premisas que ha "usado" el DM y que tienen al menos 1 suscriptor.

    Devuelve lista de (Premisa, count_suscriptores) ordenada por nombre.
    Misma definición de "usada" que `dms_que_han_usado_premisa`.
    """
    cat_ids = (
        (
            await session.execute(
                select(DMPremisa.id_premisa).where(DMPremisa.id_dm == dm_id)
            )
        ).scalars().all()
    )
    ses_ids = (
        (
            await session.execute(
                select(Sesion.id_premisa)
                .where(Sesion.id_dm == dm_id, Sesion.id_premisa.is_not(None))
                .distinct()
            )
        ).scalars().all()
    )
    usadas: set[int] = set(cat_ids) | set(ses_ids)
    if not usadas:
        return []
    result = await session.execute(
        select(Premisa, func.count(SuscripcionPremisa.id))
        .join(
            SuscripcionPremisa,
            SuscripcionPremisa.id_premisa == Premisa.id,
        )
        .where(Premisa.id.in_(usadas))
        .group_by(Premisa.id)
        .order_by(Premisa.nombre)
    )
    return [(p, c) for p, c in result.all()]


async def should_notify_subscribers(
    session: AsyncSession, sesion: Sesion
) -> bool:
    """¿Toca notificar a los suscritos al publicar esta sesión?

    Sí si la sesión:
      - no pertenece a campaña (sesión única / one-shot), o
      - es la primera sesión de su campaña.
    """
    if sesion.id_premisa is None:
        return False
    if sesion.id_campania is None:
        return True
    result = await session.execute(
        select(func.min(Sesion.id)).where(
            Sesion.id_campania == sesion.id_campania
        )
    )
    primera_id = result.scalar_one_or_none()
    return primera_id == sesion.id
