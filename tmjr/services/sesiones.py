"""Lógica de dominio sobre sesiones y apuntarse."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db.models import PJ, Sesion, SesionPJ, Persona


class SesionLlenaError(Exception):
    """Se intenta apuntar a una sesión cuyas plazas están al máximo."""



class YaApuntadoError(Exception):
    """El PJ ya está apuntado a la sesión."""


async def crear_sesion(
    session: AsyncSession,
    *,
    id_dm: int,
    id_juego: int,
    fecha: date,
    plazas_totales: int = 5,
    plazas_sin_reserva: int = 1,
    nombre: str | None = None,
    descripcion: str | None = None,
    id_premisa: int | None = None,
    id_campania: int | None = None,
    numero: int | None = None,
) -> Sesion:
    sesion = Sesion(
        id_dm=id_dm,
        id_juego=id_juego,
        fecha=fecha,
        plazas_totales=plazas_totales,
        plazas_sin_reserva=plazas_sin_reserva,
        nombre=nombre,
        descripcion=descripcion,
        id_premisa=id_premisa,
        id_campania=id_campania,
        numero=numero,
    )
    session.add(sesion)
    await session.commit()
    await session.refresh(sesion)
    return sesion


async def get_sesion(session: AsyncSession, sesion_id: int) -> Sesion | None:
    return await session.get(Sesion, sesion_id)


async def listar_sesiones_abiertas(session: AsyncSession) -> list[Sesion]:
    """Sesiones cuya fecha es hoy o futura, ordenadas por fecha asc."""
    stmt = (
        select(Sesion)
        .where(Sesion.fecha >= date.today())
        .order_by(Sesion.fecha)
    )
    return list((await session.execute(stmt)).scalars().all())


async def plazas_ocupadas(session: AsyncSession, sesion_id: int) -> int:
    """Σ (1 + acompanantes) por sesion_pj."""
    stmt = select(func.coalesce(func.sum(1 + SesionPJ.acompanantes), 0)).where(
        SesionPJ.id_sesion == sesion_id
    )
    return int((await session.execute(stmt)).scalar_one())


async def apuntar_pj(
        session: AsyncSession,
        *,
        sesion_id: int,
        pj_id: int,
        acompanantes: int = 0,
    ) -> SesionPJ:
    sesion = await session.get(Sesion, sesion_id)
    if sesion is None:
        raise ValueError(f"Sesion {sesion_id} no existe")

    pj = await session.get(PJ, pj_id)
    if pj is None:
        raise ValueError(f"PJ {pj_id} no existe")

    existente = (
        await session.execute(
            select(SesionPJ).where(
                SesionPJ.id_sesion == sesion_id, SesionPJ.id_pj == pj_id
            )
        )
    ).scalar_one_or_none()
    if existente is not None:
        raise YaApuntadoError

    ocupadas = await plazas_ocupadas(session, sesion_id)
    if ocupadas + 1 + acompanantes > sesion.plazas_totales:
        raise SesionLlenaError

    sp = SesionPJ(id_sesion=sesion_id, id_pj=pj_id, acompanantes=acompanantes)
    session.add(sp)
    await session.commit()
    await session.refresh(sp)
    return sp

async def nombre_pjs_en_sesion(session, id_session: int)->list[ str ]:
    """ Devuelve un array con los nombres de los PJs apuntados a una sesión."""
    query_nombres = (
        select(Persona.nombre)
        .join(SesionPJ, SesionPJ.id_pj == Persona.id_pj)
        .where(SesionPJ.id_sesion == id_session).
        order_by(SesionPJ.apuntada_en))
    result = await session.execute(query_nombres)
    nombres = result.scalars().all()
    return nombres



async def marcar_publicada(
      session: AsyncSession,
      sesion: Sesion,
      *,
      telegram_chat_id: str,
      telegram_thread_id: int | None,
      telegram_message_id: int,
  ) -> None:
    sesion.telegram_thread_id = telegram_thread_id
    sesion.telegram_message_id = telegram_message_id
    await session.merge(sesion)
    await session.commit()
    await session.refresh(sesion)