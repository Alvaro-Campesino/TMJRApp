"""Publica/actualiza la tarjeta de una sesión en el canal de Telegram.

Formato HTML (no Markdown): el parser legacy de Telegram tiene problemas
con guiones bajos dentro de URLs, y los deep-link a objetos llevan `_`
en el payload (`obj_premisa_42`). HTML evita esa ambigüedad.
"""
from __future__ import annotations

import logging
from html import escape

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from tmjr.config import get_settings
from tmjr.db.models import Premisa, Sesion

from .keyboards import tarjeta_sesion
from .object_links import build_object_link, get_bot_username

logger = logging.getLogger(__name__)

def _get_item_by_index(lista: list, index: int) -> str:
    """Devuelve `lista[index-1]` o "" si está fuera de rango."""
    try:
        return lista[index - 1] or ""
    except IndexError:
        return ""


def _formatear(
    sesion: Sesion,
    premisa: Premisa | None = None,
    jugadores: list[str | None] | None = None,
    *,
    dm_nombre: str | None = None,
    juego_nombre: str | None = None,
    campania_id: int | None = None,
    campania_nombre: str | None = None,
) -> str:
    """Formatea la tarjeta de una sesión en HTML.

    - El título sale de `sesion.nombre`, o si no del nombre de la premisa,
      o como último recurso `Sesión #<id>`.
    - Las descripciones de sesión y premisa se muestran ambas si existen.
    - Solo se muestra `Premisa: …` si su nombre difiere del título.
    - Si se pasan `dm_nombre`/`juego_nombre`, se renderizan como deep-link
      al objeto correspondiente.
    - Todo texto venido del usuario (nombres, descripciones) pasa por
      `html.escape` para evitar romper el parser.
    """
    jugadores = jugadores or []
    titulo = (
        sesion.nombre
        or (premisa.nombre if premisa else None)
        or f"Sesión #{sesion.id}"
    )
    lines = [f"<b>Sesión</b>: {escape(titulo)}"]

    if dm_nombre and sesion.id_dm is not None:
        lines.append(
            f"🎲 DM: {build_object_link('dm', sesion.id_dm, dm_nombre)}"
        )
    if juego_nombre and sesion.id_juego is not None:
        lines.append(
            f"🎮 Juego: {build_object_link('juego', sesion.id_juego, juego_nombre)}"
        )

    if campania_id is not None and campania_nombre:
        lines.append(
            f"🏰 Campaña: {build_object_link('campania', campania_id, campania_nombre)}"
        )

    if premisa is not None and premisa.nombre and premisa.nombre != titulo:
        lines.append(
            f"<b>Premisa</b>: {build_object_link('premisa', premisa.id, premisa.nombre)}"
        )

    if sesion.descripcion:
        lines.append(f"<b>Descripción</b>: {escape(sesion.descripcion)}")
    if premisa is not None and premisa.descripcion:
        lines.append(f"<i>{escape(premisa.descripcion)}</i>")

    lines.append("")
    lines.append(f"📅 {sesion.fecha.strftime('%Y-%m-%d %H:%M')}")
    if sesion.lugar:
        lines.append(f"📍 {escape(sesion.lugar)}")
    lines.append(f"🪑 {sesion.plazas_totales} plazas")

    lines.append("<b>Jugadores apuntados:</b>")
    for n in range(1, sesion.plazas_totales + 1):
        lines.append(f"{n}. {escape(_get_item_by_index(jugadores, n))}")

    return "\n".join(lines)


async def _resolver_contexto_card(
    sesion: Sesion,
) -> tuple[str | None, str | None, str | None]:
    """Resuelve (dm_nombre, juego_nombre, campania_nombre) para los deep-link.

    Si el username del bot no está cacheado (entornos de test sin Telegram),
    devuelve (None, None, None) sin tocar la BD.
    """
    if get_bot_username() is None:
        return None, None, None

    from tmjr.db import async_session_maker
    from tmjr.db.models import Campania, Juego, Premisa
    from tmjr.services import personas as personas_svc

    async with async_session_maker() as session:
        dm_nombre: str | None = None
        if sesion.id_dm is not None:
            persona = await personas_svc.get_persona_by_dm(session, sesion.id_dm)
            if persona is not None:
                dm_nombre = persona.nombre
        juego_nombre: str | None = None
        if sesion.id_juego is not None:
            juego = await session.get(Juego, sesion.id_juego)
            if juego is not None:
                juego_nombre = juego.nombre
        campania_nombre: str | None = None
        if sesion.id_campania is not None:
            campania = await session.get(Campania, sesion.id_campania)
            if campania is not None:
                premisa_camp = await session.get(Premisa, campania.id_premisa)
                campania_nombre = (
                    premisa_camp.nombre if premisa_camp
                    else f"Campaña #{campania.id}"
                )
    return dm_nombre, juego_nombre, campania_nombre


async def publicar_sesion(
    bot: Bot,
    sesion: Sesion,
    premisa: Premisa | None = None,
    jugadores: list[str | None] | None = None,
) -> tuple[str, int | None, int]:
    """Publica la tarjeta. Devuelve (chat_id, thread_id, message_id).

    Resuelve internamente el nombre del DM y del juego para construir los
    deep-link, así los handlers no tienen que hacer ese lookup duplicado.
    """
    s = get_settings()
    if not s.telegram_chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID no configurado")

    dm_nombre, juego_nombre, campania_nombre = await _resolver_contexto_card(sesion)

    text = _formatear(
        sesion, premisa, jugadores,
        dm_nombre=dm_nombre, juego_nombre=juego_nombre,
        campania_id=sesion.id_campania, campania_nombre=campania_nombre,
    )

    if not sesion.telegram_message_id:
        msg = await bot.send_message(
            chat_id=s.telegram_chat_id,
            message_thread_id=s.telegram_thread_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=tarjeta_sesion(sesion.id),
        )
    else:
        msg = await bot.edit_message_text(
            chat_id=s.telegram_chat_id,
            message_id=sesion.telegram_message_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=tarjeta_sesion(sesion.id),
        )
    return s.telegram_chat_id, s.telegram_thread_id, msg.message_id


async def limpiar_tarjetas_pasadas(
    bot: Bot, *, antiguedad_horas: int = 24
) -> int:
    """Borra del canal las tarjetas de sesiones cuya fecha pasó hace >X horas.

    Best-effort: si Telegram falla al borrar (mensaje ya no existe, etc.),
    se loguea pero se sigue. Limpia los telegram_*_id de la BD para no
    reintentar la próxima vez.

    Devuelve cuántas tarjetas se han limpiado.
    """
    # Imports diferidos para no acoplar el publicador al sessionmaker fuera
    # de este helper (mismo patrón que `_resolver_dm_juego`).
    from tmjr.db import async_session_maker
    from tmjr.services import sesiones as sesiones_svc

    s = get_settings()
    if not s.telegram_chat_id:
        return 0

    limpiadas = 0
    async with async_session_maker() as session:
        viejas = await sesiones_svc.list_sesiones_pasadas_publicadas(
            session, antiguedad_horas=antiguedad_horas
        )
        for v in viejas:
            try:
                await bot.delete_message(
                    chat_id=v.telegram_chat_id or s.telegram_chat_id,
                    message_id=v.telegram_message_id,
                )
            except TelegramError as e:
                logger.warning(
                    "No pude borrar tarjeta de sesión #%d: %s", v.id, e
                )
            await sesiones_svc.limpiar_publicacion(session, v)
            limpiadas += 1
    return limpiadas


