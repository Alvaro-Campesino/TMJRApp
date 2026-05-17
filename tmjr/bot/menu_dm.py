"""Mensaje fijado de "menú principal" en el DM con el bot.

Cada `/start` exitoso reescribe este mensaje:
  1. Si la persona tiene un `menu_msg_id` previo guardado, intenta
     `unpin + delete` (best-effort).
  2. Envía un mensaje con dos botones inline (Ayuda / Inicio) al DM
     de la persona.
  3. Lo fija con `disable_notification=True`.
  4. Persiste el nuevo `message_id` en `personas.menu_msg_id`.

Cualquier fallo de Telegram (chat not found, mensaje ya borrado,
permisos) se loguea y se sigue: la operación principal (/start) no se
rompe por esto.
"""
from __future__ import annotations

import logging

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from tmjr.bot.keyboards import menu_principal_inline
from tmjr.db import async_session_maker
from tmjr.db.models import Persona

logger = logging.getLogger(__name__)


_MENU_TEXT = (
    "<b>🎲 TMJR — menú principal</b>\n\n"
    "Pulsa <b>❓ Ayuda</b> para recordar cómo funciona el bot, o "
    "<b>🏠 Inicio</b> para volver al menú de cajas en cualquier momento."
)


async def fijar_menu_principal(bot: Bot, persona: Persona) -> None:
    """Reescribe el mensaje fijado del menú principal en el DM de `persona`.

    Best-effort: cada paso (unpin / delete / send / pin) puede fallar
    independientemente; se loguea y se continúa con el siguiente.
    """
    chat_id = persona.telegram_id

    # 1. Limpiar pin anterior si lo había.
    if persona.menu_msg_id is not None:
        try:
            await bot.unpin_chat_message(
                chat_id=chat_id, message_id=persona.menu_msg_id
            )
        except TelegramError as exc:
            logger.warning(
                "No pude despinar el menú anterior (persona=%s, msg=%s): %s",
                persona.id, persona.menu_msg_id, exc,
            )
        try:
            await bot.delete_message(
                chat_id=chat_id, message_id=persona.menu_msg_id
            )
        except TelegramError as exc:
            logger.warning(
                "No pude borrar el menú anterior (persona=%s, msg=%s): %s",
                persona.id, persona.menu_msg_id, exc,
            )

    # 2. Enviar nuevo mensaje.
    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=_MENU_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=menu_principal_inline(),
        )
    except TelegramError as exc:
        logger.warning(
            "No pude enviar el menú principal a persona=%s: %s",
            persona.id, exc,
        )
        return

    # 3. Fijar (silencioso).
    try:
        await bot.pin_chat_message(
            chat_id=chat_id,
            message_id=msg.message_id,
            disable_notification=True,
        )
    except TelegramError as exc:
        logger.warning(
            "No pude fijar el menú principal (persona=%s, msg=%s): %s",
            persona.id, msg.message_id, exc,
        )
        # Aun sin pin, persistimos el message_id para poder borrarlo en el
        # próximo /start y no acumular menús huérfanos.

    # 4. Persistir el message_id.
    async with async_session_maker() as session:
        persona_db = await session.get(Persona, persona.id)
        if persona_db is not None:
            persona_db.menu_msg_id = msg.message_id
            await session.commit()
