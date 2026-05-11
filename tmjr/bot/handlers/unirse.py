"""Flujo: unirse a una sesión (incluye crear perfil PJ si la persona no es PJ)."""
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

from tmjr.bot.object_links import build_object_link, get_bot_username
from tmjr.bot.publicador import publicar_sesion
from tmjr.bot.states import UnirseSesion
from tmjr.db import async_session_maker
from tmjr.db.models import PJ, Premisa, Sesion
from tmjr.services import campanias as campanias_svc
from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as sesiones_svc

logger = logging.getLogger(__name__)

END = ConversationHandler.END


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
            # Sin Persona no podemos enviar DM directamente (chat not found si
            # nunca abrió chat con el bot). Usamos un deep-link en el toast:
            # Telegram abrirá el chat privado y disparará /start apuntar_<id>,
            # que registra a la persona y le explica cómo seguir.
            bot_username = get_bot_username()
            if bot_username is not None:
                await query.answer(
                    text="Necesitas registrarte. Abre el chat conmigo.",
                    url=f"https://t.me/{bot_username}?start=apuntar_{sesion_id}",
                )
            else:
                await query.answer(
                    "Primero usa /start en privado conmigo y vuelve a pulsar Apuntarse.",
                    show_alert=True,
                )
            return END

        await query.answer()
        context.user_data["persona_id"] = persona.id

        if persona.id_pj is None:
            await context.bot.send_message(
                chat_id=user.id,
                text="Aún no estás registrado como PJ. ¿Qué nombre quieres usar? \n _el nombre se mostrará en los chats_",
                parse_mode = "Markdown",
            )
            return UnirseSesion.PJ_NOMBRE

        return await _do_apuntar(update, context, persona.id_pj)


async def pj_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nombre = (update.effective_message.text or "").strip()
    if not nombre:
        await update.effective_message.reply_text("Necesito un nombre.")
        return UnirseSesion.PJ_NOMBRE
    context.user_data["pj_nombre"] = nombre[:100]
    await update.effective_message.reply_text(
        "Si quieres puedes darnos una breve descripción sobre tí (o /skip)."
    )
    return UnirseSesion.PJ_DESC


async def pj_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.effective_message.text or ""
    desc = None if raw.strip().lower() in {"/skip", ""} else raw.strip()

    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        pj = await personas_svc.ensure_pj(
            session, persona, nombre=context.user_data["pj_nombre"], descripcion=desc
        )
    return await _do_apuntar(update, context, pj.id)


async def _notificar_dm_apuntado(
    bot: Bot,
    *,
    dm_telegram_id: int,
    pj_nombre: str,
    sesion: Sesion,
) -> None:
    """Manda un DM al máster avisando de quién se ha apuntado.

    Best-effort: si el DM nunca habló con el bot (chat not found) o cualquier
    otro error de Telegram, se loguea como warning y la operación principal
    no se rompe.
    """
    titulo = sesion.nombre or f"Sesión #{sesion.id}"
    text = (
        f"🙋 <b>{escape(pj_nombre)}</b> se ha apuntado a tu sesión "
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
            await sesiones_svc.apuntar_pj(session, sesion_id=sesion_id, pj_id=pj_id)
            sesion = await session.get(Sesion, sesion_id)
            premisa = (
                await session.get(Premisa, sesion.id_premisa)
                if sesion.id_premisa is not None else None
            )
            jugadores = await sesiones_svc.nombre_pjs_en_sesion(session, sesion.id)
            await publicar_sesion(
                context.bot, sesion, premisa=premisa, jugadores=jugadores
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
                pj = await session.get(PJ, pj_id)
                pj_nombre = pj.nombre if pj else "Alguien"
                await _notificar_dm_apuntado(
                    context.bot,
                    dm_telegram_id=dm_persona.telegram_id,
                    pj_nombre=pj_nombre,
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
            msg = f"✅ Apuntado a la sesión #{sesion_id}."


    await context.bot.send_message(chat_id=user.id, text=msg)
    return END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Cancelado.")
    return END


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(_entry, pattern=r"^apuntar_\d+$")],
        states={
            UnirseSesion.PJ_NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pj_nombre)],
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
