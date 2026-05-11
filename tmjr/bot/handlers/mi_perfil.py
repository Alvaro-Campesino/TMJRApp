"""Caja Persona → Ver perfil y Editar perfil (nombre).

Las acciones sobre el perfil de DM viven en `perfil_dm.py`.
"""
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

from tmjr.bot.states import EditarPerfil
from tmjr.db import async_session_maker
from tmjr.services import personas as personas_svc

END = ConversationHandler.END


async def ver_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muestra el perfil básico de la persona (nombre, telegram_id, roles)."""
    query = update.callback_query
    if query is not None:
        await query.answer()

    user = update.effective_user
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, user.id)

    if persona is None:
        msg = "Aún no estás registrado. Usa /start."
    else:
        roles = []
        if persona.id_master is not None:
            roles.append("DM")
        if persona.id_pj is not None:
            roles.append("PJ")
        roles_str = ", ".join(roles) if roles else "ninguno"
        msg = (
            f"*Tu perfil*\n"
            f"• Nombre: {persona.nombre}\n"
            f"• Telegram ID: `{persona.telegram_id}`\n"
            f"• Roles: {roles_str}"
        )

    await update.effective_message.reply_text(msg, parse_mode="Markdown")


# ─────────────────────────── editar nombre ────────────────────────


async def _editar_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Pide el nuevo nombre de la persona (≤100 caracteres)."""
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

    await update.effective_message.reply_text(
        "Escribe tu nuevo nombre (≤100 caracteres)."
    )
    return EditarPerfil.NOMBRE


async def _editar_nombre(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Valida y actualiza el nombre de la persona."""
    nombre = (update.effective_message.text or "").strip()
    if not nombre or len(nombre) > 100:
        await update.effective_message.reply_text(
            "Necesito un nombre no vacío de hasta 100 caracteres."
        )
        return EditarPerfil.NOMBRE

    persona_id = context.user_data["persona_id"]
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona(session, persona_id)
        await personas_svc.update_nombre(session, persona, nombre=nombre)

    await update.effective_message.reply_text(f"✅ Nombre actualizado a *{nombre}*.",
                                              parse_mode="Markdown")
    return END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fallback /cancelar para cerrar el flujo de editar nombre."""
    await update.effective_message.reply_text("Cancelado.")
    return END


def build_editar_perfil_handler() -> ConversationHandler:
    """Construye el ConversationHandler para editar el nombre de la persona."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(_editar_entry, pattern=r"^caja_persona_editar$"),
        ],
        states={
            EditarPerfil.NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _editar_nombre),
            ],
        },
        fallbacks=[CommandHandler("cancelar", _cancel)],
        name="editar_perfil",
        persistent=False,
    )
