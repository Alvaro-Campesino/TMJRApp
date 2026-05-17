"""Flujo: unirse a una sesión (crea perfil PJ si la persona no es PJ).

El **nombre del PJ es siempre el de la `Persona`** (no se persiste
aparte). Por eso, cuando la persona no tiene PJ todavía, solo le
preguntamos la descripción del PJ (con la información sobre límites de
contenido). No hay paso "elige tu nombre de PJ".
"""
from __future__ import annotations

import logging
from html import escape

from telegram import Bot, Update
from telegram.error import TelegramError
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tmjr.bot.notificaciones import notificar_cruce_minimo_si_aplica
from tmjr.bot.object_links import build_object_link
from tmjr.bot.publicador import publicar_sesion
from tmjr.bot.states import UnirseSesion
from tmjr.db import async_session_maker
from tmjr.db.models import Premisa, Sesion
from tmjr.services import campanias as campanias_svc
from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as sesiones_svc

logger = logging.getLogger(__name__)

END = ConversationHandler.END


_PEDIR_DESC = (
    "Aún no estás registrado como PJ. Escríbenos una breve descripción "
    "para que el DM te conozca: cómo es tu personaje y, sobre todo, "
    "los <b>límites de contenido</b> que necesitas (temas a evitar, "
    "intensidad, etc.). Usa /skip si prefieres dejarlo en blanco."
)


async def _entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        await update.effective_message.reply_text(
            "Pulsa el botón 'Apuntarse' en la tarjeta de la sesión que te interese."
        )
        return END

    sesion_id = int(query.data.split("_", 1)[1])
    context.user_data["sesion_id"] = sesion_id

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None:
            await query.answer(
                "🔒 Aún no estás registrado. Pulsa el botón del mensaje "
                "fijado del canal para unirte al bot.",
                show_alert=True,
            )
            return END

        await query.answer()
        context.user_data["persona_id"] = persona.id

        if persona.id_pj is None:
            await context.bot.send_message(
                chat_id=user.id,
                text=_PEDIR_DESC,
                parse_mode="HTML",
            )
            return UnirseSesion.PJ_DESC

        return await _do_apuntar(update, context, persona.id_pj)


async def pj_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la descripción del PJ y crea el perfil PJ enlazado a la persona.

    El nombre del PJ es el de la persona; aquí solo persistimos la
    descripción (que incluye los límites de contenido).
    """
    raw = update.effective_message.text or ""
    desc = None if raw.strip().lower() in {"/skip", ""} else raw.strip()

    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        pj = await personas_svc.ensure_pj(session, persona, descripcion=desc)
    return await _do_apuntar(update, context, pj.id)


def _link_a_mensaje_publicado(sesion: Sesion) -> str | None:
    """Construye la URL `t.me/c/<chat>/[<thread>/]<msg>` del mensaje del canal.

    Devuelve None si la sesión no está publicada o el chat_id no tiene el
    formato esperado de supergroup/canal (`-100…`). Los chats privados o
    grupos clásicos no son enlazables vía t.me y caen en este None.
    """
    chat_id = sesion.telegram_chat_id
    msg_id = sesion.telegram_message_id
    if not chat_id or not msg_id:
        return None
    raw = chat_id.lstrip("-")
    # Los supergroups/channels tienen chat_id `-100XXXXXXXXXX`; t.me usa
    # solo la parte `XXXXXXXXXX`. Si no empieza por 100 no podemos
    # construir el enlace porque no es un chat tipo canal/supergroup.
    if not raw.startswith("100"):
        return None
    raw = raw[3:]
    if not raw:
        return None
    thread = sesion.telegram_thread_id
    if thread:
        return f"https://t.me/c/{raw}/{thread}/{msg_id}"
    return f"https://t.me/c/{raw}/{msg_id}"


async def _notificar_dm_apuntado(
    bot: Bot,
    *,
    dm_telegram_id: int,
    pj_nombre: str,
    pj_id: int,
    sesion: Sesion,
) -> None:
    """Manda un DM al máster avisando de quién se ha apuntado.

    El nombre del PJ se envuelve en deep-link a su ficha
    (`obj_pj_<id>`) para que el DM pueda consultar la descripción del
    PJ (incluidos sus límites de contenido) pulsando sobre el nombre.

    Best-effort: si el DM nunca habló con el bot (chat not found) o
    cualquier otro error de Telegram, se loguea como warning y la
    operación principal no se rompe.
    """
    titulo = sesion.nombre or f"Sesión #{sesion.id}"
    pj_link = build_object_link("pj", pj_id, pj_nombre)
    text = (
        f"🙋 {pj_link} se ha apuntado a tu sesión "
        f"{build_object_link('sesion', sesion.id, titulo)}\n"
        f"📅 {sesion.fecha.strftime('%Y-%m-%d %H:%M')}"
    )
    try:
        await bot.send_message(
            chat_id=dm_telegram_id, text=text, parse_mode="HTML"
        )
    except TelegramError as e:
        logger.warning(
            "No pude notificar al DM (telegram_id=%s): %s", dm_telegram_id, e
        )


async def _do_apuntar(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pj_id: int
) -> int:
    sesion_id = context.user_data["sesion_id"]
    user = update.effective_user
    async with async_session_maker() as session:
        try:
            ocupadas_antes = await sesiones_svc.plazas_ocupadas(
                session, sesion_id
            )
            await sesiones_svc.apuntar_pj(session, sesion_id=sesion_id, pj_id=pj_id)
            sesion = await session.get(Sesion, sesion_id)
            ocupadas_despues = await sesiones_svc.plazas_ocupadas(
                session, sesion_id
            )
            premisa = (
                await session.get(Premisa, sesion.id_premisa)
                if sesion.id_premisa is not None else None
            )
            jugadores = await sesiones_svc.nombre_pjs_en_sesion(session, sesion.id)
            await publicar_sesion(
                context.bot, sesion, premisa=premisa, jugadores=jugadores
            )
            await notificar_cruce_minimo_si_aplica(
                context.bot, sesion,
                ocupadas_antes=ocupadas_antes,
                ocupadas_despues=ocupadas_despues,
            )

            # Si esta sesión es la primera de una campaña, el PJ que se
            # acaba de apuntar pasa a ser fijo de la campaña.
            if sesion.id_campania is not None and (sesion.numero or 0) == 1:
                await campanias_svc.add_pj_fijo(
                    session, id_campania=sesion.id_campania, id_pj=pj_id
                )

            # Notificar al DM (saltar si es el mismo usuario que se apunta).
            dm_persona = await personas_svc.get_persona_by_dm(session, sesion.id_dm)
            if dm_persona is not None and dm_persona.telegram_id != user.id:
                # El nombre del PJ es el de la persona enlazada.
                persona_pj = await personas_svc.get_persona_by_pj(session, pj_id)
                pj_nombre = persona_pj.nombre if persona_pj else "Alguien"
                await _notificar_dm_apuntado(
                    context.bot,
                    dm_telegram_id=dm_persona.telegram_id,
                    pj_nombre=pj_nombre,
                    pj_id=pj_id,
                    sesion=sesion,
                )

        except sesiones_svc.YaApuntadoError:
            msg = "Ya estabas apuntado a esta sesión."
        except sesiones_svc.SesionLlenaError:
            msg = "La sesión está llena."
        except ValueError as e:
            msg = f"Error: {e}"
        except Exception as e:
            msg = f"Error: {e}"
        else:
            titulo = (
                sesion.nombre
                or (premisa.nombre if premisa else None)
                or f"Sesión #{sesion.id}"
            )
            fecha_str = sesion.fecha.strftime("%Y-%m-%d")
            hora_str = sesion.fecha.strftime("%H:%M")
            url = _link_a_mensaje_publicado(sesion)
            if url is not None:
                titulo_html = f'<a href="{url}">{escape(titulo)}</a>'
            else:
                titulo_html = f"<b>{escape(titulo)}</b>"
            msg = (
                f"✅ Apuntado a la sesión: {titulo_html}, "
                f"del día: {fecha_str} y hora: {hora_str}"
            )

    await context.bot.send_message(
        chat_id=user.id, text=msg, parse_mode="HTML"
    )
    return END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Cancelado.")
    return END


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(_entry, pattern=r"^apuntar_\d+$")],
        states={
            UnirseSesion.PJ_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, pj_desc),
                CommandHandler("skip", pj_desc),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        name="unirse_sesion",
        persistent=False,
        per_chat=False,
    )
