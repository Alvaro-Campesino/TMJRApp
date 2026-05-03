"""Dispatcher de las cajas del ReplyKeyboard.

Cuando el usuario pulsa una de las 5 cajas del teclado persistente, llega un
mensaje de texto con el label de la caja. Este handler responde con el
submenú inline (Crear / Listar / Editar) correspondiente.
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tmjr.bot.keyboards import (
    CAJA_CAMPANIA,
    CAJA_JUEGOS,
    CAJA_PERSONA,
    CAJA_PREMISA,
    CAJA_SESION,
    submenu_objeto,
)

_CAJA_TO_OBJ = {
    CAJA_PERSONA: ("persona", "👤 Persona"),
    CAJA_SESION: ("sesion", "🎲 Sesión"),
    CAJA_PREMISA: ("premisa", "📜 Premisa"),
    CAJA_CAMPANIA: ("campania", "🏰 Campaña"),
    CAJA_JUEGOS: ("juegos", "🎮 Juegos"),
}


async def caja_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.effective_message.text or "").strip()
    entry = _CAJA_TO_OBJ.get(text)
    if entry is None:
        return
    obj, titulo = entry
    await update.effective_message.reply_text(
        f"{titulo} — ¿qué quieres hacer?",
        reply_markup=submenu_objeto(obj),
    )
