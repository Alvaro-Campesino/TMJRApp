"""Catch-all para callbacks `caja_*` y comandos cuyo flujo aún no existe."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


async def proximamente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is not None:
        await query.answer()
    await update.effective_message.reply_text(
        "🚧 Próximamente. Esta opción todavía no está disponible."
    )
