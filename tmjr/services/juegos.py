"""Lógica de dominio sobre el catálogo de juegos y la lista por DM."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db.models import DM, DMJuego, Juego


async def list_all_juegos(session: AsyncSession) -> list[Juego]:
    """Catálogo global, ordenado alfabéticamente por nombre."""
    result = await session.execute(select(Juego).order_by(Juego.nombre))
    return list(result.scalars().all())


async def list_juegos_for_dm(session: AsyncSession, id_dm: int) -> list[Juego]:
    """Juegos enlazados a un DM concreto."""
    result = await session.execute(
        select(Juego)
        .join(DMJuego, DMJuego.id_juego == Juego.id)
        .where(DMJuego.id_dm == id_dm)
        .order_by(Juego.nombre)
    )
    return list(result.scalars().all())


async def list_juegos_not_in_dm(
    session: AsyncSession, id_dm: int
) -> list[Juego]:
    """Catálogo global menos los juegos que el DM ya tiene en su lista."""
    sub = select(DMJuego.id_juego).where(DMJuego.id_dm == id_dm)
    result = await session.execute(
        select(Juego).where(~Juego.id.in_(sub)).order_by(Juego.nombre)
    )
    return list(result.scalars().all())


async def find_juego_by_name(session: AsyncSession, nombre: str) -> Juego | None:
    """Búsqueda case-insensitive en el catálogo global."""
    result = await session.execute(
        select(Juego).where(func.lower(Juego.nombre) == nombre.strip().lower())
    )
    return result.scalar_one_or_none()


async def create_juego(
    session: AsyncSession,
    *,
    nombre: str,
    descripcion: str | None = None,
) -> Juego:
    """Crea entrada en el catálogo global. UNIQUE constraint en nombre."""
    juego = Juego(nombre=nombre.strip(), descripcion=descripcion)
    session.add(juego)
    await session.commit()
    await session.refresh(juego)
    return juego


async def get_or_create_juego(
    session: AsyncSession,
    *,
    nombre: str,
) -> tuple[Juego, bool]:
    """Devuelve (juego, created). Idempotente por nombre case-insensitive."""
    existing = await find_juego_by_name(session, nombre)
    if existing is not None:
        return existing, False
    juego = await create_juego(session, nombre=nombre)
    return juego, True


async def add_juego_to_dm(
    session: AsyncSession,
    *,
    id_dm: int,
    id_juego: int,
) -> bool:
    """Enlaza juego al DM. Devuelve True si lo añadió, False si ya existía."""
    existing = (
        await session.execute(
            select(DMJuego).where(
                DMJuego.id_dm == id_dm, DMJuego.id_juego == id_juego
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False

    if (await session.get(DM, id_dm)) is None:
        raise ValueError(f"DM {id_dm} no existe")
    if (await session.get(Juego, id_juego)) is None:
        raise ValueError(f"Juego {id_juego} no existe")

    session.add(DMJuego(id_dm=id_dm, id_juego=id_juego))
    await session.commit()
    return True
