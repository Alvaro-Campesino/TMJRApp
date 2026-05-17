"""Dispatcher de las cajas del ReplyKeyboard.

Cuando el usuario pulsa una de las 5 cajas del teclado persistente, llega un
mensaje de texto con el label de la caja. Este handler responde con el
submenú inline (Crear / Listar / Editar) correspondiente.

Las cajas Persona y Sesión son dinámicas: su submenú depende de si la
persona ya tiene perfil de DM o no.
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
    submenu_persona,
    submenu_sesion,
)
from tmjr.db import async_session_maker
from tmjr.services import personas as personas_svc

_CAJA_TO_OBJ = {
    CAJA_PERSONA: ("persona", "👤 Persona"),
    CAJA_SESION: ("sesion", "🎲 Sesión"),
    CAJA_PREMISA: ("premisa", "📜 Premisa"),
    CAJA_CAMPANIA: ("campania", "🏰 Campaña"),
    CAJA_JUEGOS: ("juegos", "🎮 Juegos"),
}


async def caja_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde a la pulsación de una caja del ReplyKeyboard mostrando su submenú."""
    text = (update.effective_message.text or "").strip()
    entry = _CAJA_TO_OBJ.get(text)
    if entry is None:
        return
    obj, titulo = entry

    if obj == "persona":
        kb = submenu_persona(es_dm=await _es_dm(update.effective_user.id))
    elif obj == "sesion":
        kb = submenu_sesion(es_dm=await _es_dm(update.effective_user.id))
    else:
        kb = submenu_objeto(obj)

    await update.effective_message.reply_text(
        f"{titulo} — ¿qué quieres hacer?",
        reply_markup=kb,
    )


async def _es_dm(telegram_id: int) -> bool:
    """¿La persona vinculada a este telegram_id tiene perfil de DM?

    Si la persona aún no se ha registrado (no existe en BD), devuelve
    False — el flujo de DM/edición empuja al usuario a /start.
    """
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, telegram_id)
    return persona is not None and persona.id_master is not None
