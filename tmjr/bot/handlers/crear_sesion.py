"""Flujo: crear sesión (incluye crear perfil DM si la persona no es DM)."""
from __future__ import annotations

from datetime import date

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
from tmjr.bot.states import CrearSesion
from tmjr.db import async_session_maker
from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as sesiones_svc

END = ConversationHandler.END


async def _entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)
        if persona is None:
            await update.effective_message.reply_text(
                "Primero usa /start para registrarte."
            )
            return END
        context.user_data["persona_id"] = persona.id

        if persona.id_master is None:
            await update.effective_message.reply_text(
                "Aún no eres DM. Cuéntame en una frase tu experiencia como máster (o /skip)."
            )
            return CrearSesion.DM_BIO

    await update.effective_message.reply_text(
        "¿Qué fecha quieres? Formato: AAAA-MM-DD"
    )
    return CrearSesion.FECHA


async def dm_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bio = update.effective_message.text or ""
    if bio.strip().lower() in {"/skip", ""}:
        bio = None

    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        await personas_svc.ensure_dm(session, persona, biografia=bio)

    await update.effective_message.reply_text(
        "✅ Perfil de DM creado.\n¿Qué fecha quieres para la sesión? (AAAA-MM-DD)"
    )
    return CrearSesion.FECHA


async def fecha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text or "").strip()
    try:
        f = date.fromisoformat(raw)
    except ValueError:
        await update.effective_message.reply_text("Formato no válido. Usa AAAA-MM-DD.")
        return CrearSesion.FECHA

    context.user_data["fecha"] = f
    await update.effective_message.reply_text("¿Cuántas plazas? (1-6)")
    return CrearSesion.PLAZAS


async def plazas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = (update.effective_message.text or "").strip()
    try:
        n = int(raw)
        assert 1 <= n <= 6
    except (ValueError, AssertionError):
        await update.effective_message.reply_text("Tiene que ser un número entre 1 y 6.")
        return CrearSesion.PLAZAS

    context.user_data["plazas"] = n
    persona_id = context.user_data["persona_id"]

    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        sesion = await sesiones_svc.crear_sesion(
            session,
            id_dm=persona.id_master,
            fecha=context.user_data["fecha"],
            plazas_totales=n,
        )
        try:
            await publicar_sesion(context.bot, sesion)
        except RuntimeError as e:
            await update.effective_message.reply_text(
                f"Sesión creada (#{sesion.id}) pero no se pudo publicar: {e}"
            )
            return END

    await update.effective_message.reply_text(
        f"✅ Sesión #{sesion.id} creada y publicada en el canal."
    )
    return END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Cancelado.")
    return END


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(_entry, pattern=r"^crear_sesion$"),
            CommandHandler("crear_sesion", _entry),
        ],
        states={
            CrearSesion.DM_BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, dm_bio),
                                 CommandHandler("skip", dm_bio)],
            CrearSesion.FECHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, fecha)],
            CrearSesion.PLAZAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, plazas)],
        },
        fallbacks=[CommandHandler("cancelar", cancel)],
        name="crear_sesion",
        persistent=False,
    )
