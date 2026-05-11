"""Dispatcher de las cajas del ReplyKeyboard.

Cuando el usuario pulsa una de las 5 cajas del teclado persistente, llega un
mensaje de texto con el label de la caja. Este handler responde con el
submenú inline (Crear / Listar / Editar) correspondiente.

La caja Persona es especial: su submenú es dinámico y depende de si la
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
        kb = await _submenu_persona_para_user(update.effective_user.id)
    else:
        kb = submenu_objeto(obj)

    await update.effective_message.reply_text(
        f"{titulo} — ¿qué quieres hacer?",
        reply_markup=kb,
    )


async def _submenu_persona_para_user(telegram_id: int):
    """Construye el submenú de Persona consultando si la persona es DM.

    Si la persona aún no se ha registrado (no existe en BD), tratamos el
    caso como 'no es DM' — el botón 'Crear perfil DM' avisará al usuario
    de que primero debe usar /start.
    """
    async with async_session_maker() as session:
        persona = await personas_svc.get_persona_by_telegram(session, telegram_id)
    es_dm = persona is not None and persona.id_master is not None
    return submenu_persona(es_dm=es_dm)
