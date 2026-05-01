"""Construye la Application de python-telegram-bot y registra los handlers."""
from __future__ import annotations

from telegram.ext import Application, CommandHandler

from tmjr.config import get_settings

from .handlers.crear_sesion import build_handler as build_crear_sesion
from .handlers.start import start
from .handlers.unirse import build_handler as build_unirse


def build_application() -> Application:
    settings = get_settings()
    application = (
        Application.builder()
        .token(settings.telegram_token)
        .updater(None)  # webhook, no polling
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(build_crear_sesion())
    application.add_handler(build_unirse())

    return application
