"""Lógica de dominio sobre campañas y PJs fijos."""
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db.models import Campania, CampaniaPJFijo, PJ, Persona, Sesion, SesionPJ


async def crear_campania(
    session: AsyncSession,
    *,
    id_dm: int,
    id_premisa: int,
) -> Campania:
    """Crea la campaña asociada a una premisa y un DM."""
    campania = Campania(id_dm=id_dm, id_premisa=id_premisa)
    session.add(campania)
    await session.commit()
    await session.refresh(campania)
    return campania


async def get_campania(session: AsyncSession, campania_id: int) -> Campania | None:
    """Devuelve la campaña por id, o None si no existe."""
    return await session.get(Campania, campania_id)


async def list_campanias_for_dm(
    session: AsyncSession, id_dm: int
) -> list[Campania]:
    """Campañas del DM ordenadas por fecha de creación descendente."""
    stmt = (
        select(Campania)
        .where(Campania.id_dm == id_dm)
        .order_by(Campania.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def next_numero(session: AsyncSession, id_campania: int) -> int:
    """Siguiente número de sesión dentro de la campaña (1, 2, 3, ...)."""
    stmt = select(Sesion.numero).where(Sesion.id_campania == id_campania)
    numeros = [n for (n,) in (await session.execute(stmt)).all() if n is not None]
    return (max(numeros) + 1) if numeros else 1


# ─────────────────────── PJs fijos de la campaña ──────────────────


async def add_pj_fijo(
    session: AsyncSession,
    *,
    id_campania: int,
    id_pj: int,
) -> bool:
    """Añade un PJ a `campania_pjs_fijos`. Idempotente: True si lo añade,
    False si ya estaba.
    """
    existing = (
        await session.execute(
            select(CampaniaPJFijo).where(
                CampaniaPJFijo.id_campania == id_campania,
                CampaniaPJFijo.id_pj == id_pj,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False
    session.add(CampaniaPJFijo(id_campania=id_campania, id_pj=id_pj))
    await session.commit()
    return True


async def remove_pj_fijo(
    session: AsyncSession,
    *,
    id_campania: int,
    id_pj: int,
) -> bool:
    """Quita un PJ de `campania_pjs_fijos` y de las sesiones futuras de
    la campaña (sesion.fecha >= hoy). Las sesiones pasadas se conservan
    como histórico.

    Devuelve True si quitó el fijo, False si no estaba.
    """
    existing = (
        await session.execute(
            select(CampaniaPJFijo).where(
                CampaniaPJFijo.id_campania == id_campania,
                CampaniaPJFijo.id_pj == id_pj,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        return False

    # Borrar de sesion_pj de las sesiones futuras de esta campaña.
    hoy_00 = datetime.combine(date.today(), time.min)
    sesiones_futuras_ids = (
        await session.execute(
            select(Sesion.id).where(
                Sesion.id_campania == id_campania,
                Sesion.fecha >= hoy_00,
            )
        )
    ).scalars().all()
    if sesiones_futuras_ids:
        await session.execute(
            delete(SesionPJ).where(
                SesionPJ.id_sesion.in_(sesiones_futuras_ids),
                SesionPJ.id_pj == id_pj,
            )
        )

    await session.delete(existing)
    await session.commit()
    return True


async def list_pjs_fijos(
    session: AsyncSession, id_campania: int
) -> list[PJ]:
    """PJs fijos de la campaña, ordenados por nombre."""
    stmt = (
        select(PJ)
        .join(CampaniaPJFijo, CampaniaPJFijo.id_pj == PJ.id)
        .where(CampaniaPJFijo.id_campania == id_campania)
        .order_by(PJ.nombre)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_pjs_no_fijos(
    session: AsyncSession, id_campania: int
) -> list[PJ]:
    """PJs registrados que NO son fijos de la campaña — para el picker
    'Añadir PJ a la campaña'.
    """
    sub = select(CampaniaPJFijo.id_pj).where(
        CampaniaPJFijo.id_campania == id_campania
    )
    stmt = select(PJ).where(~PJ.id.in_(sub)).order_by(PJ.nombre)
    return list((await session.execute(stmt)).scalars().all())


# ─────────────────────── Materialización en sesión ────────────────


async def materializar_pjs_a_sesion(
    session: AsyncSession, sesion: Sesion
) -> int:
    """Crea filas `sesion_pj` para todos los PJs fijos de la campaña.

    Idempotente: si una fila ya existe (mismo id_sesion + id_pj), se
    salta. No respeta `plazas_totales` — los fijos van por delante de
    los apuntados manuales. Devuelve cuántos se materializaron.
    """
    if sesion.id_campania is None:
        return 0
    fijos = await list_pjs_fijos(session, sesion.id_campania)
    if not fijos:
        return 0
    existentes = set(
        (
            await session.execute(
                select(SesionPJ.id_pj).where(SesionPJ.id_sesion == sesion.id)
            )
        ).scalars().all()
    )
    nuevos = 0
    for pj in fijos:
        if pj.id in existentes:
            continue
        session.add(SesionPJ(id_sesion=sesion.id, id_pj=pj.id))
        nuevos += 1
    if nuevos:
        await session.commit()
    return nuevos


async def list_telegram_de_pjs_fijos(
    session: AsyncSession, id_campania: int
) -> list[tuple[int, str]]:
    """Devuelve (telegram_id, pj.nombre) para cada PJ fijo de la campaña.

    Útil para mandar DM al publicar una nueva sesión.
    """
    stmt = (
        select(Persona.telegram_id, PJ.nombre)
        .select_from(CampaniaPJFijo)
        .join(PJ, PJ.id == CampaniaPJFijo.id_pj)
        .join(Persona, Persona.id_pj == PJ.id)
        .where(CampaniaPJFijo.id_campania == id_campania)
    )
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]
