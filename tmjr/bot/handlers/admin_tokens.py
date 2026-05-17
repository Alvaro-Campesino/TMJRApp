"""Comandos admin: /rotar_token y /publicar_pin.

Acceso restringido a `Settings.admin_telegram_ids`. El pin del canal lleva
un único botón URL que dispara el deep-link `?start=invitacion_<token>`;
al rotar el token, se edita ese mismo mensaje (no se vuelve a fijar).
"""
from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from tmjr.bot.object_links import get_bot_username
from tmjr.config import get_settings
from tmjr.db import async_session_maker
from tmjr.db.models import TokenInvitacion
from tmjr.services import app_config as config_svc
from tmjr.services import tokens as tokens_svc

logger = logging.getLogger(__name__)


def _es_admin(telegram_id: int) -> bool:
    return telegram_id in get_settings().admin_telegram_ids


def _deep_link_invitacion(token: str) -> str | None:
    """`https://t.me/<bot>?start=invitacion_<token>` si conocemos el username."""
    username = get_bot_username()
    return f"https://t.me/{username}?start=invitacion_{token}" if username else None


def _pin_keyboard(token: str) -> InlineKeyboardMarkup | None:
    url = _deep_link_invitacion(token)
    if url is None:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔑 Unirme al bot", url=url)]]
    )


_PIN_TEXT = (
    "<b>👋 Bienvenida</b>\n\n"
    "Pulsa el botón para registrarte en el bot del grupo. "
    "Solo así podrás apuntarte a las sesiones que se publiquen aquí."
)


async def rotar_token(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Genera un nuevo token de invitación. Solo admins.

    Tras rotar, intenta editar el botón del pin existente (si lo hay) para
    que apunte al deep-link nuevo.
    """
    user = update.effective_user
    if user is None or not _es_admin(user.id):
        await update.effective_message.reply_text("No autorizado.")
        return

    settings = get_settings()
    async with async_session_maker() as session:
        ttl = settings.token_rotation_days
        tok = await tokens_svc.crear_token(
            session,
            creador_telegram_id=user.id,
            ttl_dias=ttl,
        )
        pin_message_id = await config_svc.get(session, config_svc.PIN_MESSAGE_ID)

    deep_link = _deep_link_invitacion(tok.token) or "(bot_username no cacheado)"
    msg_lines = [
        "✅ Token rotado.",
        f"<code>{tok.token}</code>",
        f"Deep-link: {deep_link}",
    ]
    if tok.expires_at is not None:
        msg_lines.append(f"Caduca: {tok.expires_at.isoformat(timespec='minutes')}")

    pin_chat_id = settings.telegram_chat_id
    if pin_message_id and pin_chat_id:
        kb = _pin_keyboard(tok.token)
        if kb is not None:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=pin_chat_id,
                    message_id=int(pin_message_id),
                    reply_markup=kb,
                )
                msg_lines.append("Pin actualizado con el nuevo botón.")
            except TelegramError as e:
                logger.warning("No pude actualizar el pin: %s", e)
                msg_lines.append(f"⚠️ Pin sin actualizar: {e}")
    else:
        msg_lines.append("ℹ️ Aún no hay pin publicado (usa /publicar_pin).")

    await update.effective_message.reply_text(
        "\n".join(msg_lines), parse_mode="HTML"
    )


async def publicar_pin(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Publica (o reemplaza) el mensaje fijado del canal con el botón
    de invitación al token activo. Solo admins.
    """
    user = update.effective_user
    if user is None or not _es_admin(user.id):
        await update.effective_message.reply_text("No autorizado.")
        return

    settings = get_settings()
    if not settings.telegram_chat_id:
        await update.effective_message.reply_text(
            "TELEGRAM_CHAT_ID no configurado."
        )
        return

    async with async_session_maker() as session:
        activo = await tokens_svc.token_activo(session)
        if activo is None:
            # Sin token: lo creamos al vuelo para no obligar al admin a
            # llamar /rotar_token antes — el pin sin botón no sirve.
            activo = await tokens_svc.crear_token(
                session,
                creador_telegram_id=user.id,
                ttl_dias=settings.token_rotation_days,
            )

        kb = _pin_keyboard(activo.token)
        if kb is None:
            await update.effective_message.reply_text(
                "Aún no tengo el username del bot cacheado, espera unos "
                "segundos tras arrancar y reintenta."
            )
            return

        # Borrar pin anterior si existía (best-effort).
        pin_previo = await config_svc.get(session, config_svc.PIN_MESSAGE_ID)
        if pin_previo:
            try:
                await context.bot.unpin_chat_message(
                    chat_id=settings.telegram_chat_id,
                    message_id=int(pin_previo),
                )
            except TelegramError as e:
                logger.warning("No pude despinar el mensaje previo: %s", e)

        try:
            msg = await context.bot.send_message(
                chat_id=settings.telegram_chat_id,
                message_thread_id=settings.telegram_thread_id,
                text=_PIN_TEXT,
                parse_mode="HTML",
                reply_markup=kb,
            )
            await context.bot.pin_chat_message(
                chat_id=settings.telegram_chat_id,
                message_id=msg.message_id,
                disable_notification=True,
            )
        except TelegramError as e:
            await update.effective_message.reply_text(
                f"Fallo enviando/fijando el mensaje: {e}"
            )
            return

        await config_svc.set_(
            session, config_svc.PIN_MESSAGE_ID, str(msg.message_id)
        )

    await update.effective_message.reply_text(
        f"✅ Pin publicado (message_id={msg.message_id})."
    )


async def actualizar_pin_con_token_activo(bot) -> bool:
    """Edita el botón del pin para que apunte al token activo actual.

    Pensado para job de APScheduler tras rotar el token. Best-effort:
    devuelve True si se editó, False si faltaba algún requisito o
    Telegram falló.
    """
    settings = get_settings()
    if not settings.telegram_chat_id:
        return False

    async with async_session_maker() as session:
        activo = await tokens_svc.token_activo(session)
        pin_message_id = await config_svc.get(session, config_svc.PIN_MESSAGE_ID)

    if activo is None or not pin_message_id:
        return False

    kb = _pin_keyboard(activo.token)
    if kb is None:
        return False

    try:
        await bot.edit_message_reply_markup(
            chat_id=settings.telegram_chat_id,
            message_id=int(pin_message_id),
            reply_markup=kb,
        )
        return True
    except TelegramError as e:
        logger.warning("No pude actualizar el pin: %s", e)
        return False
