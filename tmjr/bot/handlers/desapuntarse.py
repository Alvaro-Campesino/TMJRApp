"""Borrarse de una sesión.

Handler one-shot: el usuario pulsa el botón 🚪   de la tarjeta de
la sesión publicada en el canal y se elimina su SesionPJ. Tras borrar
republicamos la tarjeta para que se actualice el listado de jugadores.
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tmjr.bot.notificaciones import notificar_cruce_minimo_si_aplica
from tmjr.bot.publicador import publicar_sesion
from tmjr.db import async_session_maker
from tmjr.db.models import Premisa, Sesion
from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as sesiones_svc


async def desapuntarse(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Resuelve el callback `desapuntar_<sesion_id>`.

    Identifica al usuario, obtiene su PJ y lo borra de la sesión. Si no
    estaba apuntado o ni siquiera tiene perfil de PJ, devuelve un toast
    informativo sin tocar nada.
    """
    query = update.callback_query
    sesion_id = int(query.data.removeprefix("desapuntar_"))
    user = update.effective_user

    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None or persona.id_pj is None:
            await query.answer("No estás apuntado a esta sesión.", show_alert=True)
            return

        ocupadas_antes = await sesiones_svc.plazas_ocupadas(
            session, sesion_id
        )
        try:
            await sesiones_svc.desapuntar_pj(
                session, sesion_id=sesion_id, pj_id=persona.id_pj
            )
        except sesiones_svc.NoApuntadoError:
            await query.answer("No estás apuntado a esta sesión.", show_alert=True)
            return

        sesion = await session.get(Sesion, sesion_id)
        ocupadas_despues = await sesiones_svc.plazas_ocupadas(
            session, sesion_id
        )
        premisa = (
            await session.get(Premisa, sesion.id_premisa)
            if sesion.id_premisa is not None
            else None
        )
        jugadores = await sesiones_svc.nombre_pjs_en_sesion(session, sesion.id)

    await query.answer("✅ Te he borrado de la sesión.")
    await publicar_sesion(
        context.bot, sesion, premisa=premisa, jugadores=jugadores
    )
    await notificar_cruce_minimo_si_aplica(
        context.bot, sesion,
        ocupadas_antes=ocupadas_antes,
        ocupadas_despues=ocupadas_despues,
    )
