"""Caja Persona → Ver mi perfil."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tmjr.db import async_session_maker
from tmjr.services import personas as personas_svc


async def ver_perfil(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
