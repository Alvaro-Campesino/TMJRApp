"""Lógica de dominio sobre sesiones y apuntarse."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db.models import LimiteSesion, PJ, PJEnEspera, Persona, Sesion, SesionPJ


class SesionLlenaError(Exception):
    """Se intenta apuntar a una sesión cuyas plazas están al máximo."""



class YaApuntadoError(Exception):
    """El PJ ya está apuntado a la sesión."""


class NoApuntadoError(Exception):
    """Se intenta borrar a un PJ que no estaba apuntado a la sesión."""


async def crear_sesion(
    session: AsyncSession,
    *,
    id_dm: int,
    id_juego: int,
    fecha: datetime,
    plazas_totales: int = 5,
    plazas_sin_reserva: int = 1,
    nombre: str | None = None,
    descripcion: str | None = None,
    lugar: str | None = None,
    id_premisa: int | None = None,
    id_campania: int | None = None,
    numero: int | None = None,
) -> Sesion:
    """Crea y persiste una sesión. Devuelve la entidad refrescada."""
    sesion = Sesion(
        id_dm=id_dm,
        id_juego=id_juego,
        fecha=fecha,
        plazas_totales=plazas_totales,
        plazas_sin_reserva=plazas_sin_reserva,
        nombre=nombre,
        descripcion=descripcion,
        lugar=lugar,
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


async def list_sesiones_for_dm(
    session: AsyncSession, id_dm: int, *, only_future: bool = True
) -> list[Sesion]:
    """Sesiones del DM, por defecto solo futuras (>= hoy 00:00)."""
    stmt = select(Sesion).where(Sesion.id_dm == id_dm)
    if only_future:
        hoy_00 = datetime.combine(date.today(), time.min)
        stmt = stmt.where(Sesion.fecha >= hoy_00)
    stmt = stmt.order_by(Sesion.fecha)
    return list((await session.execute(stmt)).scalars().all())


async def update_sesion(
    session: AsyncSession,
    sesion: Sesion,
    *,
    nombre: str | None = None,
    descripcion: str | None = None,
    lugar: str | None = None,
    fecha: datetime | None = None,
    plazas_totales: int | None = None,
) -> Sesion:
    """Actualiza campos de una sesión. Solo modifica los kwargs no-None.

    Si se cambian las plazas, valida que no queden por debajo de las ya
    ocupadas (suma de 1 + acompanantes por SesionPJ).
    """
    if plazas_totales is not None:
        ocupadas = await plazas_ocupadas(session, sesion.id)
        if plazas_totales < ocupadas:
            raise ValueError(
                f"No puedo bajar a {plazas_totales} plazas: ya hay {ocupadas} ocupadas"
            )
        sesion.plazas_totales = plazas_totales
    if nombre is not None:
        sesion.nombre = nombre
    if descripcion is not None:
        sesion.descripcion = descripcion
    if lugar is not None:
        sesion.lugar = lugar
    if fecha is not None:
        sesion.fecha = fecha

    await session.commit()
    await session.refresh(sesion)
    return sesion


async def list_sesiones_pasadas_publicadas(
    session: AsyncSession, *, antiguedad_horas: int = 24
) -> list[Sesion]:
    """Sesiones cuya fecha pasó hace más de `antiguedad_horas` y siguen publicadas.

    Útil para limpiar tarjetas viejas del canal cuando se publica una nueva.
    """
    umbral = datetime.now() - timedelta(hours=antiguedad_horas)
    stmt = select(Sesion).where(
        Sesion.fecha < umbral,
        Sesion.telegram_message_id.is_not(None),
    )
    return list((await session.execute(stmt)).scalars().all())


async def apuntados_telegram(
    session: AsyncSession, sesion_id: int
) -> list[tuple[int, str]]:
    """Devuelve (telegram_id, pj.nombre) por cada PJ apuntado a la sesión.

    Útil para notificar por DM al cancelar/borrar una sesión.
    """
    stmt = (
        select(Persona.telegram_id, PJ.nombre)
        .select_from(SesionPJ)
        .join(PJ, PJ.id == SesionPJ.id_pj)
        .join(Persona, Persona.id_pj == PJ.id)
        .where(SesionPJ.id_sesion == sesion_id)
    )
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def borrar_sesion(session: AsyncSession, sesion: Sesion) -> None:
    """Borra la sesión y todas sus filas dependientes en una sola transacción.

    Cubre `sesion_pj`, `pjs_en_espera` y `limites_sesion`. Además borra
    los PJ "invitados" (PJ.id_anfitrion IS NOT NULL) que estaban
    apuntados a esta sesión — su ciclo de vida está atado al SesionPJ
    que los creó. NO toca la tarjeta del canal.
    """
    invitado_ids = (
        await session.execute(
            select(PJ.id)
            .join(SesionPJ, SesionPJ.id_pj == PJ.id)
            .where(SesionPJ.id_sesion == sesion.id)
            .where(PJ.id_anfitrion.is_not(None))
        )
    ).scalars().all()

    await session.execute(
        delete(SesionPJ).where(SesionPJ.id_sesion == sesion.id)
    )
    await session.execute(
        delete(PJEnEspera).where(PJEnEspera.id_sesion == sesion.id)
    )
    await session.execute(
        delete(LimiteSesion).where(LimiteSesion.id_sesion == sesion.id)
    )
    if invitado_ids:
        await session.execute(delete(PJ).where(PJ.id.in_(invitado_ids)))
    await session.delete(sesion)
    await session.commit()


async def limpiar_publicacion(session: AsyncSession, sesion: Sesion) -> None:
    """Limpia los identificadores de Telegram de la sesión (tarjeta borrada)."""
    sesion.telegram_chat_id = None
    sesion.telegram_thread_id = None
    sesion.telegram_message_id = None
    await session.merge(sesion)
    await session.commit()


async def listar_sesiones_abiertas(session: AsyncSession) -> list[Sesion]:
    """Sesiones cuya fecha es hoy o futura, ordenadas por fecha asc."""
    hoy_00 = datetime.combine(date.today(), time.min)
    stmt = (
        select(Sesion)
        .where(Sesion.fecha >= hoy_00)
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

async def add_invitado(
    session: AsyncSession,
    *,
    sesion_id: int,
    anfitrion_pj_id: int,
    anfitrion_nombre_visible: str,
) -> PJ:
    """Crea un PJ invitado del anfitrión y lo apunta a la sesión.

    Lanza `SesionLlenaError` si añadirlo excedería las plazas. El nombre
    del invitado es `"Invitado-<nombre>"` (cap a 100 chars total porque
    PJ.nombre es VARCHAR(100); el truncado a 20 chars para la tarjeta lo
    aplica `nombre_pjs_en_sesion`).
    """
    sesion = await session.get(Sesion, sesion_id)
    if sesion is None:
        raise ValueError(f"Sesion {sesion_id} no existe")
    if (await session.get(PJ, anfitrion_pj_id)) is None:
        raise ValueError(f"PJ {anfitrion_pj_id} (anfitrión) no existe")

    ocupadas = await plazas_ocupadas(session, sesion_id)
    if ocupadas + 1 > sesion.plazas_totales:
        raise SesionLlenaError

    nombre = f"Invitado-{anfitrion_nombre_visible}"[:100]
    invitado = PJ(nombre=nombre, id_anfitrion=anfitrion_pj_id)
    session.add(invitado)
    await session.flush()  # asigna invitado.id

    sp = SesionPJ(id_sesion=sesion_id, id_pj=invitado.id)
    session.add(sp)
    await session.commit()
    await session.refresh(invitado)
    return invitado


async def remove_ultimo_invitado(
    session: AsyncSession,
    *,
    sesion_id: int,
    anfitrion_pj_id: int,
) -> bool:
    """Borra el último invitado del anfitrión apuntado a la sesión (LIFO
    por `apuntada_en`). Devuelve True si quitó alguno, False si no había.
    """
    stmt = (
        select(SesionPJ, PJ)
        .join(PJ, PJ.id == SesionPJ.id_pj)
        .where(SesionPJ.id_sesion == sesion_id)
        .where(PJ.id_anfitrion == anfitrion_pj_id)
        .order_by(SesionPJ.apuntada_en.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return False
    sp, pj = row
    await session.delete(sp)
    await session.delete(pj)
    await session.commit()
    return True


async def desapuntar_pj(
        session: AsyncSession,
        *,
        sesion_id: int,
        pj_id: int,
    ) -> None:
    """Borra al PJ de la sesión. Lanza NoApuntadoError si no estaba apuntado."""
    existente = (
        await session.execute(
            select(SesionPJ).where(
                SesionPJ.id_sesion == sesion_id, SesionPJ.id_pj == pj_id
            )
        )
    ).scalar_one_or_none()
    if existente is None:
        raise NoApuntadoError

    await session.delete(existente)
    await session.commit()


async def nombre_pjs_en_sesion(session, id_session: int) -> list[str]:
    """Nombres de los apuntados a una sesión, en orden de apuntada_en.

    Para los PJ normales devuelve el nombre de la `Persona` propietaria.
    Para los invitados (PJ.id_anfitrion IS NOT NULL) no hay Persona, así
    que devuelve `PJ.nombre` truncado a 20 caracteres — el formato
    `"Invitado-<nombre>"` que se almacena en `add_invitado` ya viene listo
    para encajar en el slot de la tarjeta.
    """
    from sqlalchemy import case

    nombre_expr = case(
        (PJ.id_anfitrion.is_not(None), func.substr(PJ.nombre, 1, 20)),
        else_=Persona.nombre,
    )
    stmt = (
        select(nombre_expr)
        .select_from(SesionPJ)
        .join(PJ, PJ.id == SesionPJ.id_pj)
        .outerjoin(Persona, Persona.id_pj == PJ.id)
        .where(SesionPJ.id_sesion == id_session)
        .order_by(SesionPJ.apuntada_en)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())



async def marcar_publicada(
      session: AsyncSession,
      sesion: Sesion,
      *,
      telegram_chat_id: str,
      telegram_thread_id: int | None,
      telegram_message_id: int,
  ) -> None:
    """Persiste los identificadores de Telegram en la sesión publicada."""
    sesion.telegram_chat_id = telegram_chat_id
    sesion.telegram_thread_id = telegram_thread_id
    sesion.telegram_message_id = telegram_message_id
    await session.merge(sesion)
    await session.commit()
    await session.refresh(sesion)