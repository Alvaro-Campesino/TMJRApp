"""Botones ➕1 / ➖1 de la tarjeta de sesión: invitados sin Telegram.

Un "invitado" es un acompañante anónimo del anfitrión: se cuenta en
`sesion_pj.acompanantes` de la fila del anfitrión. No hay PJ propio.
Desaparece al pulsar -1, al desapuntarse el anfitrión o al borrar la
sesión.

Comportamiento:
  - mas1: si el usuario no tiene Persona/PJ, toast redirigiéndolo al pin
    del canal para registrarse con el token de invitación (REU-45). Si
    está registrado pero no apuntado, toast pidiendo apuntarse primero.
    Si está apuntado, suma 1 acompañante y republica la tarjeta.
  - menos1: resta 1 acompañante al anfitrión. Si no tenía, toast
    informativo.

Republica la tarjeta tras cada cambio para refrescar la lista de
jugadores.
"""
from __future__ import annotations

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from tmjr.bot.notificaciones import notificar_cruce_minimo_si_aplica
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
            await query.answer(
                "🔒 Aún no estás registrado. Pulsa el botón del mensaje "
                "fijado del canal para unirte al bot.",
                show_alert=True,
            )
            return

        ocupadas_antes = await sesiones_svc.plazas_ocupadas(
            session, sesion_id
        )
        try:
            await sesiones_svc.add_invitado(
                session,
                sesion_id=sesion_id,
                anfitrion_pj_id=persona.id_pj,
            )
        except sesiones_svc.AnfitrionNoApuntadoError:
            await query.answer(
                "Apúntate primero antes de traer invitados.", show_alert=True
            )
            return
        except sesiones_svc.SesionLlenaError:
            await query.answer("La sesión está llena.", show_alert=True)
            return
        except ValueError as e:
            await query.answer(f"Error: {e}", show_alert=True)
            return

        sesion = await session.get(Sesion, sesion_id)
        ocupadas_despues = await sesiones_svc.plazas_ocupadas(
            session, sesion_id
        )

    await query.answer(f"✅ Invitado añadido: Invitado-{persona.nombre[:11]}")
    await _republicar(context, sesion)
    await notificar_cruce_minimo_si_aplica(
        context.bot, sesion,
        ocupadas_antes=ocupadas_antes,
        ocupadas_despues=ocupadas_despues,
    )


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

        ocupadas_antes = await sesiones_svc.plazas_ocupadas(
            session, sesion_id
        )
        removed = await sesiones_svc.remove_ultimo_invitado(
            session, sesion_id=sesion_id, anfitrion_pj_id=persona.id_pj
        )
        sesion = await session.get(Sesion, sesion_id)
        ocupadas_despues = await sesiones_svc.plazas_ocupadas(
            session, sesion_id
        )

    if not removed:
        await query.answer(
            "No tienes invitados en esta sesión.", show_alert=True
        )
        return
    await query.answer("✅ Invitado eliminado.")
    await _republicar(context, sesion)
    await notificar_cruce_minimo_si_aplica(
        context.bot, sesion,
        ocupadas_antes=ocupadas_antes,
        ocupadas_despues=ocupadas_despues,
    )
