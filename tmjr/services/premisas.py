"""Lógica de dominio sobre premisas (concepto / título de partida)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db.models import Juego, Premisa


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


async def get_premisa(session: AsyncSession, premisa_id: int) -> Premisa | None:
    return await session.get(Premisa, premisa_id)
