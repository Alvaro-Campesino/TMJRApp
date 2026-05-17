"""APScheduler para jobs periódicos del bot.

Hoy hospeda un único job opcional: rotación automática del token de
invitación cada `TOKEN_ROTATION_DAYS` días. Si la variable no se
configura, el scheduler no se arranca.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot

from tmjr.bot.handlers.admin_tokens import actualizar_pin_con_token_activo
from tmjr.config import get_settings
from tmjr.db import async_session_maker
from tmjr.services import tokens as tokens_svc

logger = logging.getLogger(__name__)


async def _job_rotar_token(bot: Bot) -> None:
    """Rota el token y refresca el pin. Best-effort: cualquier fallo se loguea."""
    settings = get_settings()
    try:
        async with async_session_maker() as session:
            tok = await tokens_svc.crear_token(
                session,
                creador_telegram_id=None,
                ttl_dias=settings.token_rotation_days,
            )
        actualizado = await actualizar_pin_con_token_activo(bot)
        logger.warning(
            "Token rotado automáticamente: id=%s pin_actualizado=%s",
            tok.id,
            actualizado,
        )
    except Exception:
        logger.exception("Fallo en el job de rotación automática de token")


def build_scheduler(bot: Bot) -> AsyncIOScheduler | None:
    """Crea (no arranca) el scheduler si TOKEN_ROTATION_DAYS está configurado."""
    settings = get_settings()
    days = settings.token_rotation_days
    if not days or days <= 0:
        logger.warning(
            "TOKEN_ROTATION_DAYS no configurado → sin rotación automática."
        )
        return None

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _job_rotar_token,
        trigger="interval",
        days=days,
        args=[bot],
        id="rotar_token",
        replace_existing=True,
    )
    logger.warning(
        "Scheduler configurado: rotar_token cada %d días.", days
    )
    return scheduler
