"""/start — crea o recupera la persona en BD y muestra el menú principal."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from tmjr.db import async_session_maker
from tmjr.services import personas as svc

from ..keyboards import menu_principal


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return

    nombre = user.full_name or user.username or f"persona_{user.id}"
    async with async_session_maker() as session:
        persona, created = await svc.get_or_create_persona(
            session, telegram_id=user.id, nombre=nombre
        )

    saludo = (
        f"¡Hola, {persona.nombre}! Te he registrado."
        if created
        else f"¡Hola de nuevo, {persona.nombre}!"
    )
    await update.effective_message.reply_text(
        f"{saludo}\n\n¿Qué quieres hacer?",
        reply_markup=menu_principal(),
    )
