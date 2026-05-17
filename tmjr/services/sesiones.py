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


class AnfitrionNoApuntadoError(Exception):
    """El anfitrión intenta traer un invitado pero no está apuntado a la sesión."""


async def crear_sesion(
    session: AsyncSession,
    *,
    id_dm: int,
    id_juego: int,
    fecha: datetime,
    plazas_totales: int = 5,
    plazas_minimas: int = 0,
    plazas_sin_reserva: int = 1,
    nombre: str | None = None,
    descripcion: str | None = None,
    lugar: str | None = None,
    id_premisa: int | None = None,
    id_campania: int | None = None,
    numero: int | None = None,
) -> Sesion:
    """Crea y persiste una sesión. Devuelve la entidad refrescada."""
    if plazas_minimas < 0 or plazas_minimas > plazas_totales:
        raise ValueError(
            f"plazas_minimas debe estar en [0, {plazas_totales}], "
            f"recibido {plazas_minimas}"
        )
    sesion = Sesion(
        id_dm=id_dm,
        id_juego=id_juego,
        fecha=fecha,
        plazas_totales=plazas_totales,
        plazas_minimas=plazas_minimas,
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


def cruce_minimo(
    ocupadas_antes: int, ocupadas_despues: int, plazas_minimas: int
) -> str | None:
    """Detecta si se ha cruzado el umbral mínimo entre dos estados.

    - "arriba": antes < min y después >= min.
    - "abajo":  antes >= min y después < min.
    - None:     no hay cruce, o `plazas_minimas == 0` (siempre alcanzado).

    Pensado para que los handlers que apuntan/desapuntan llamen a
    `plazas_ocupadas` antes y después de su operación, comparen con el
    `plazas_minimas` de la sesión y, si esta función devuelve algo
    distinto de None, notifiquen al DM.
    """
    if plazas_minimas <= 0:
        return None
    if ocupadas_antes < plazas_minimas <= ocupadas_despues:
        return "arriba"
    if ocupadas_despues < plazas_minimas <= ocupadas_antes:
        return "abajo"
    return None


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
    plazas_minimas: int | None = None,
) -> Sesion:
    """Actualiza campos de una sesión. Solo modifica los kwargs no-None.

    Si se cambian las plazas, valida que no queden por debajo de las ya
    ocupadas (suma de 1 + acompanantes por SesionPJ). Si se cambia el
    mínimo, valida que esté en `[0, plazas_totales]` (con el nuevo total
    si se está cambiando a la vez).
    """
    nuevo_total = (
        plazas_totales if plazas_totales is not None else sesion.plazas_totales
    )
    nuevo_min = (
        plazas_minimas if plazas_minimas is not None else sesion.plazas_minimas
    )
    if nuevo_min < 0 or nuevo_min > nuevo_total:
        raise ValueError(
            f"plazas_minimas debe estar en [0, {nuevo_total}], recibido {nuevo_min}"
        )
    if plazas_totales is not None:
        ocupadas = await plazas_ocupadas(session, sesion.id)
        if plazas_totales < ocupadas:
            raise ValueError(
                f"No puedo bajar a {plazas_totales} plazas: ya hay {ocupadas} ocupadas"
            )
        sesion.plazas_totales = plazas_totales
    if plazas_minimas is not None:
        sesion.plazas_minimas = plazas_minimas
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
    """Devuelve (telegram_id, persona.nombre) por cada PJ apuntado a la sesión.

    El nombre del PJ es siempre el de la persona (no hay PJ.nombre).
    Útil para notificar por DM al cancelar/borrar una sesión.
    """
    stmt = (
        select(Persona.telegram_id, Persona.nombre)
        .select_from(SesionPJ)
        .join(Persona, Persona.id_pj == SesionPJ.id_pj)
        .where(SesionPJ.id_sesion == sesion_id)
    )
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def borrar_sesion(session: AsyncSession, sesion: Sesion) -> None:
    """Borra la sesión y todas sus filas dependientes en una sola transacción.

    Cubre `sesion_pj`, `pjs_en_espera` y `limites_sesion`. Los invitados
    son solo un contador en `sesion_pj.acompanantes`, así que desaparecen
    al borrar la fila de sesion_pj — no hay PJ que limpiar. NO toca la
    tarjeta del canal.
    """
    await session.execute(
        delete(SesionPJ).where(SesionPJ.id_sesion == sesion.id)
    )
    await session.execute(
        delete(PJEnEspera).where(PJEnEspera.id_sesion == sesion.id)
    )
    await session.execute(
        delete(LimiteSesion).where(LimiteSesion.id_sesion == sesion.id)
    )
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
) -> SesionPJ:
    """Suma un acompañante a la fila SesionPJ del anfitrión en la sesión.

    Los invitados no son PJ propios: son solo un contador en
    `sesion_pj.acompanantes` de la fila del anfitrión. Esto exige que el
    anfitrión esté apuntado a la sesión — si no lo está, lanzamos
    `AnfitrionNoApuntadoError`. Si añadir un acompañante excedería las
    plazas totales, lanzamos `SesionLlenaError`.
    """
    sesion = await session.get(Sesion, sesion_id)
    if sesion is None:
        raise ValueError(f"Sesion {sesion_id} no existe")
    if (await session.get(PJ, anfitrion_pj_id)) is None:
        raise ValueError(f"PJ {anfitrion_pj_id} (anfitrión) no existe")

    sp = (
        await session.execute(
            select(SesionPJ)
            .where(SesionPJ.id_sesion == sesion_id)
            .where(SesionPJ.id_pj == anfitrion_pj_id)
        )
    ).scalar_one_or_none()
    if sp is None:
        raise AnfitrionNoApuntadoError

    ocupadas = await plazas_ocupadas(session, sesion_id)
    if ocupadas + 1 > sesion.plazas_totales:
        raise SesionLlenaError

    sp.acompanantes += 1
    await session.commit()
    await session.refresh(sp)
    return sp


async def remove_ultimo_invitado(
    session: AsyncSession,
    *,
    sesion_id: int,
    anfitrion_pj_id: int,
) -> bool:
    """Decrementa en 1 los acompañantes del anfitrión en la sesión.

    Devuelve True si había acompañantes (y se restó uno), False si el
    anfitrión no estaba apuntado o tenía 0 acompañantes.
    """
    sp = (
        await session.execute(
            select(SesionPJ)
            .where(SesionPJ.id_sesion == sesion_id)
            .where(SesionPJ.id_pj == anfitrion_pj_id)
        )
    ).scalar_one_or_none()
    if sp is None or sp.acompanantes <= 0:
        return False
    sp.acompanantes -= 1
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
    """Devuelve un nombre por slot ocupado de la sesión.

    Por cada `SesionPJ` (ordenado por `apuntada_en`) emite primero el
    nombre de la `Persona` del PJ, y a continuación `acompanantes`
    entradas con el formato `"Invitado-<persona.nombre>"` truncado a 20
    caracteres. Así cada acompañante ocupa su slot numérico en la
    tarjeta de la sesión.
    """
    slots = await slots_pjs_en_sesion(session, id_session)
    return [nombre for nombre, _ in slots]


async def slots_pjs_en_sesion(
    session, id_session: int
) -> list[tuple[str, int | None]]:
    """Como `nombre_pjs_en_sesion`, pero con el `pj.id` real por slot.

    Cada slot es `(nombre_a_mostrar, pj_id | None)`:
      - PJ apuntado real → `(persona.nombre, pj.id)`.
      - Acompañante sin Telegram → `("Invitado-<host>"[:20], None)` (no
        son PJs reales, solo contador del anfitrión).

    Lo usa el render con deep-links (vista "Mis sesiones" del DM); para
    el canal y el listado público se sigue usando `nombre_pjs_en_sesion`.
    """
    stmt = (
        select(Persona.nombre, SesionPJ.id_pj, SesionPJ.acompanantes)
        .select_from(SesionPJ)
        .join(Persona, Persona.id_pj == SesionPJ.id_pj)
        .where(SesionPJ.id_sesion == id_session)
        .order_by(SesionPJ.apuntada_en)
    )
    rows = (await session.execute(stmt)).all()
    slots: list[tuple[str, int | None]] = []
    for nombre, pj_id, acompanantes in rows:
        slots.append((nombre, pj_id))
        if acompanantes:
            invitado = f"Invitado-{nombre}"[:20]
            slots.extend([(invitado, None)] * acompanantes)
    return slots



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