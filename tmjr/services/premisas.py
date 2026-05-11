"""Lógica de dominio sobre premisas (concepto / título de partida)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db.models import DM, DMPremisa, Juego, Premisa


async def crear_premisa(
    session: AsyncSession,
    *,
    nombre: str,
    id_juego: int | None = None,
    descripcion: str | None = None,
    aviso_contenido: str | None = None,
) -> Premisa:
    """Crea una premisa (titulo + juego + descripción). One-shot o reutilizable."""
    if id_juego is not None and (await session.get(Juego, id_juego)) is None:
        raise ValueError(f"Juego {id_juego} no existe")

    premisa = Premisa(
        nombre=nombre.strip(),
        id_juego=id_juego,
        descripcion=descripcion,
        aviso_contenido=aviso_contenido,
    )
    session.add(premisa)
    await session.commit()
    await session.refresh(premisa)
    return premisa


async def update_premisa(
    session: AsyncSession,
    premisa: Premisa,
    *,
    nombre: str | None = None,
    descripcion: str | None = None,
    aviso_contenido: str | None = None,
    id_juego: int | None = None,
) -> Premisa:
    """Actualiza campos de una premisa. Solo modifica los kwargs no-None.

    Si se cambia `id_juego`, valida que el juego existe en el catálogo.
    """
    if id_juego is not None and (await session.get(Juego, id_juego)) is None:
        raise ValueError(f"Juego {id_juego} no existe")
    if nombre is not None:
        premisa.nombre = nombre
    if descripcion is not None:
        premisa.descripcion = descripcion
    if aviso_contenido is not None:
        premisa.aviso_contenido = aviso_contenido
    if id_juego is not None:
        premisa.id_juego = id_juego

    await session.commit()
    await session.refresh(premisa)
    return premisa


async def get_premisa(session: AsyncSession, premisa_id: int) -> Premisa | None:
    """Devuelve la premisa por id, o None si no existe."""
    return await session.get(Premisa, premisa_id)


async def list_all_premisas(session: AsyncSession) -> list[Premisa]:
    """Catálogo global de premisas, ordenado alfabéticamente por nombre."""
    result = await session.execute(select(Premisa).order_by(Premisa.nombre))
    return list(result.scalars().all())


async def list_premisas_for_dm(
    session: AsyncSession, id_dm: int
) -> list[Premisa]:
    """Premisas enlazadas al DM (vía `dm_premisas`), ordenadas por nombre."""
    result = await session.execute(
        select(Premisa)
        .join(DMPremisa, DMPremisa.id_premisa == Premisa.id)
        .where(DMPremisa.id_dm == id_dm)
        .order_by(Premisa.nombre)
    )
    return list(result.scalars().all())


async def list_premisas_not_in_dm(
    session: AsyncSession, id_dm: int
) -> list[Premisa]:
    """Premisas globales que el DM aún no tiene enlazadas."""
    sub = select(DMPremisa.id_premisa).where(DMPremisa.id_dm == id_dm)
    result = await session.execute(
        select(Premisa).where(~Premisa.id.in_(sub)).order_by(Premisa.nombre)
    )
    return list(result.scalars().all())


async def link_premisa_to_dm(
    session: AsyncSession,
    *,
    id_dm: int,
    id_premisa: int,
) -> bool:
    """Enlaza una premisa al DM en `dm_premisas`.

    Idempotente: devuelve True si crea el enlace, False si ya existía.
    Valida que tanto el DM como la premisa existan antes de insertar.
    """
    existing = (
        await session.execute(
            select(DMPremisa).where(
                DMPremisa.id_dm == id_dm, DMPremisa.id_premisa == id_premisa
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False

    if (await session.get(DM, id_dm)) is None:
        raise ValueError(f"DM {id_dm} no existe")
    if (await session.get(Premisa, id_premisa)) is None:
        raise ValueError(f"Premisa {id_premisa} no existe")

    session.add(DMPremisa(id_dm=id_dm, id_premisa=id_premisa))
    await session.commit()
    return True
