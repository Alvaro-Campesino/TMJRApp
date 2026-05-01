"""Publica/actualiza la tarjeta de una sesión en el canal de Telegram."""
from __future__ import annotations

from telegram import Bot
from telegram.constants import ParseMode

from tmjr.config import get_settings
from tmjr.db.models import Sesion

from .keyboards import tarjeta_sesion


def _formatear(sesion: Sesion) -> str:
    return (
        f"*Sesión #{sesion.id}*\n"
        f"📅 {sesion.fecha.isoformat()}\n"
        f"🪑 {sesion.plazas_totales} plazas "
        f"({sesion.plazas_sin_reserva} sin reserva)\n"
    )


async def publicar_sesion(bot: Bot, sesion: Sesion) -> tuple[str, int | None, int]:
    """Publica la tarjeta. Devuelve (chat_id, thread_id, message_id)."""
    s = get_settings()
    if not s.telegram_chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID no configurado")

    msg = await bot.send_message(
        chat_id=s.telegram_chat_id,
        message_thread_id=s.telegram_thread_id,
        text=_formatear(sesion),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=tarjeta_sesion(sesion.id),
    )
    return s.telegram_chat_id, s.telegram_thread_id, msg.message_id
