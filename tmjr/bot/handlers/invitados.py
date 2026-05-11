"""Botones ➕1 / ➖1 de la tarjeta de sesión: invitados sin Telegram.

Un "invitado" es un PJ con `id_anfitrion` apuntando al PJ del anfitrión
(quien pulsó +1). Vive solo mientras esté apuntado a esa sesión: cuando
el anfitrión pulsa -1 o se borra la sesión, el PJ invitado desaparece.

Comportamiento:
  - mas1: si el usuario no tiene Persona/PJ, deep-link a /start
    apuntar_<id> igual que el botón Apuntarse. Si lo tiene, crea el
    invitado, lo apunta y republica la tarjeta.
  - menos1: borra el último invitado del anfitrión (LIFO por
    `apuntada_en`). Si no hay, toast informativo.

Republica la tarjeta tras cada cambio para refrescar la lista de
jugadores.
"""
from __future__ import annotations

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from tmjr.bot.object_links import get_bot_username
from tmjr.bot.publicador import publicar_sesion
from tmjr.db import async_session_maker
from tmjr.db.models import Premisa, Sesion
from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as sesiones_svc


async def _republicar(context, sesion: Sesion) -> None:
    """Re-publica la tarjeta de la sesión tras un cambio de jugadores."""
    async with async_session_maker() as session:
        sesion = await session.get(Sesion, sesion.id)
        premisa = (
            await session.get(Premisa, sesion.id_premisa)
            if sesion.id_premisa is not None else None
        )
        jugadores = await sesiones_svc.nombre_pjs_en_sesion(session, sesion.id)
    try:
        await publicar_sesion(
            context.bot, sesion, premisa=premisa, jugadores=jugadores
        )
    except TelegramError:
        # Si la tarjeta ya no existe en el canal (borrada manualmente, etc.)
        # no rompemos el flujo del +1/-1.
        pass


async def mas1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Crea un invitado del usuario y lo apunta a la sesión."""
    query = update.callback_query
    sesion_id = int(query.data.removeprefix("mas1_"))
    user = update.effective_user

    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_pj is None:
            # Mismo recurso que en unirse: deep-link al chat para registrarse.
            bot_username = get_bot_username()
            if bot_username is not None:
                await query.answer(
                    text="Necesitas registrarte para traer invitados.",
                    url=f"https://t.me/{bot_username}?start=apuntar_{sesion_id}",
                )
            else:
                await query.answer(
                    "Primero usa /start en privado conmigo y vuelve a intentarlo.",
                    show_alert=True,
                )
            return

        try:
            invitado = await sesiones_svc.add_invitado(
                session,
                sesion_id=sesion_id,
                anfitrion_pj_id=persona.id_pj,
                anfitrion_nombre_visible=persona.nombre[:80],
            )
        except sesiones_svc.SesionLlenaError:
            await query.answer("La sesión está llena.", show_alert=True)
            return
        except ValueError as e:
            await query.answer(f"Error: {e}", show_alert=True)
            return

        sesion = await session.get(Sesion, sesion_id)

    await query.answer(f"✅ Añadido: {invitado.nombre}")
    await _republicar(context, sesion)


async def menos1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Borra el último invitado del anfitrión apuntado a la sesión."""
    query = update.callback_query
    sesion_id = int(query.data.removeprefix("menos1_"))
    user = update.effective_user

    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_pj is None:
            await query.answer(
                "No tienes invitados en esta sesión.", show_alert=True
            )
            return

        removed = await sesiones_svc.remove_ultimo_invitado(
            session, sesion_id=sesion_id, anfitrion_pj_id=persona.id_pj
        )
        sesion = await session.get(Sesion, sesion_id)

    if not removed:
        await query.answer(
            "No tienes invitados en esta sesión.", show_alert=True
        )
        return
    await query.answer("✅ Invitado eliminado.")
    await _republicar(context, sesion)
