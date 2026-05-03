"""Construye la Application de python-telegram-bot y registra los handlers.

- `build_application()` (default): bot en modo webhook (sin updater).
- `build_application(polling=True)`: bot en modo polling, para dev local
  (sin necesidad de webhook ni cert).
"""
from __future__ import annotations

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from tmjr.config import get_settings

from .handlers.cajas import caja_dispatcher
from .handlers.crear_sesion import build_handler as build_crear_sesion
from .handlers.help import help_command
from .handlers.listar_juegos import listar_juegos
from .handlers.listar_sesiones import listar_sesiones
from .handlers.mi_perfil import ver_perfil
from .handlers.proximamente import proximamente
from .handlers.start import start
from .handlers.unirse import build_handler as build_unirse
from .keyboards import CAJAS

# Comandos sugeridos en el menú nativo de Telegram (pulsa "/" en el chat).
# Se incluyen los que aún no están implementados con etiqueta "(próx.)" para
# no rehacer set_my_commands cada fase. Los handlers que falten responden
# "🚧 Próximamente" via el catch-all proximamente.
BOT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Registrarte / menú principal"),
    BotCommand("help", "Cómo funciona el bot"),
    BotCommand("crear_sesion", "Crear una nueva sesión"),
    BotCommand("listar_sesiones", "Ver sesiones abiertas"),
    BotCommand("listar_juegos", "Ver juegos del catálogo"),
    BotCommand("mi_perfil", "Ver tu persona"),
    BotCommand("crear_premisa", "Crear una premisa (próx.)"),
    BotCommand("listar_premisas", "Listar premisas (próx.)"),
    BotCommand("crear_campania", "Crear una campaña (próx.)"),
    BotCommand("listar_campanias", "Listar campañas (próx.)"),
    BotCommand("cancelar", "Cancelar flujo en curso"),
]


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)


def _register_handlers(application: Application) -> None:
    # Comandos directos.
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("listar_sesiones", listar_sesiones))
    application.add_handler(CommandHandler("listar_juegos", listar_juegos))
    application.add_handler(CommandHandler("mi_perfil", ver_perfil))
    # Comandos "próximamente" — responden con stub mientras no estén listos.
    for cmd in (
        "crear_premisa",
        "listar_premisas",
        "crear_campania",
        "listar_campanias",
    ):
        application.add_handler(CommandHandler(cmd, proximamente))

    # ConversationHandlers (deben ir antes del MessageHandler de cajas para
    # que sus filters.TEXT capturen primero los mensajes durante un flujo).
    application.add_handler(build_crear_sesion())
    application.add_handler(build_unirse())

    # Callbacks de los submenús inline.
    application.add_handler(
        CallbackQueryHandler(ver_perfil, pattern=r"^caja_persona_ver$")
    )
    application.add_handler(
        CallbackQueryHandler(listar_sesiones, pattern=r"^caja_sesion_listar$")
    )
    application.add_handler(
        CallbackQueryHandler(listar_juegos, pattern=r"^caja_juegos_listar$")
    )
    # Catch-all para los caja_*_* aún no implementados (Persona/Editar,
    # Premisa/*, Campania/*, Juegos/{Crear,Editar}, Sesion/Editar).
    # Ojo: caja_sesion_crear lo absorbe primero el ConversationHandler de
    # crear_sesion porque está registrado antes.
    application.add_handler(CallbackQueryHandler(proximamente, pattern=r"^caja_"))

    # Cajas del ReplyKeyboard: el usuario pulsa "👤 Persona", llega como texto.
    cajas_regex = r"^(" + "|".join(CAJAS) + r")$"
    application.add_handler(
        MessageHandler(filters.Regex(cajas_regex), caja_dispatcher)
    )


def build_application(*, polling: bool = False) -> Application:
    settings = get_settings()
    builder = (
        Application.builder()
        .token(settings.telegram_token)
        .post_init(_post_init)
    )
    if not polling:
        builder = builder.updater(None)  # webhook: no polling
    application = builder.build()
    _register_handlers(application)
    return application