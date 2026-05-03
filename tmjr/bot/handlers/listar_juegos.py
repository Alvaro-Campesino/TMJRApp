"""Caja Juegos → Listar catálogo / comando /listar_juegos."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tmjr.db import async_session_maker
from tmjr.services import juegos as juegos_svc


async def listar_juegos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is not None:
        await query.answer()

    async with async_session_maker() as session:
        juegos = await juegos_svc.list_all_juegos(session)

    if not juegos:
        await update.effective_message.reply_text(
            "El catálogo de juegos está vacío. Cuando alguien cree una sesión "
            "y añada un juego nuevo, aparecerá aquí."
        )
        return

    lines = [f"*Catálogo de juegos* ({len(juegos)}):"]
    for j in juegos:
        lines.append(f"• {j.nombre}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")
