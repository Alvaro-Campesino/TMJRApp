"""Flujo: unirse a una sesión (incluye crear perfil PJ si la persona no es PJ)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tmjr.bot.publicador import publicar_sesion
from tmjr.bot.states import UnirseSesion
from tmjr.db import async_session_maker
from tmjr.db.models import Sesion, Premisa
from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as sesiones_svc
from tmjr.bot.publicador import publicar_sesion

END = ConversationHandler.END


async def _entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        await update.effective_message.reply_text(
            "Pulsa el botón 'Apuntarse' en la tarjeta de la sesión que te interese."
        )
        return END

    await query.answer()
    sesion_id = int(query.data.split("_", 1)[1])
    context.user_data["sesion_id"] = sesion_id

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None:
            await context.bot.send_message(
                chat_id=user.id,
                text="Primero usa /start en privado para registrarte.",
            )
            return END
        context.user_data["persona_id"] = persona.id

        if persona.id_pj is None:
            await context.bot.send_message(
                chat_id=user.id,
                text="Aún no estás registrado como PJ. ¿Qué nombre quieres usar? \n _el nombre se mostrará en los chats_",
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


async def _do_apuntar(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pj_id: int
) -> int:
    sesion_id = context.user_data["sesion_id"]
    async with async_session_maker() as session:
        try:
            await sesiones_svc.apuntar_pj(session, sesion_id=sesion_id, pj_id=pj_id)
            sesion = await session.get(Sesion, sesion_id)
            premisa = await session.get(Premisa, sesion.id_premisa)
            jugadores = await sesiones_svc.nombre_pjs_en_sesion(session, sesion.id)
            await publicar_sesion(context.bot, sesion, jugadores, premisa=premisa)

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


    user = update.effective_user
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
