"""Construye la Application de python-telegram-bot y registra los handlers.

- `build_application()` (default): bot en modo webhook (sin updater).
- `build_application(polling=True)`: bot en modo polling, para dev local
  (sin necesidad de webhook ni cert).
"""
from __future__ import annotations

from telegram import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import logging

from tmjr.config import get_settings

from .handlers.admin_tokens import publicar_pin, rotar_token
from .handlers.cajas import caja_dispatcher
from .handlers.crear_premisa import build_handler as build_crear_premisa
from .handlers.crear_sesion import build_handler as build_crear_sesion
from .handlers.desapuntarse import desapuntarse
from .handlers.editar_premisa import build_handler as build_editar_premisa
from .handlers.editar_sesion import build_handler as build_editar_sesion
from .handlers.gestionar_campania import build_handler as build_gestionar_campania
from .handlers.help import help_command
from .handlers.info_campania import info_campania
from .handlers.invitados import mas1, menos1
from .handlers.listar_juegos import listar_juegos
from .handlers.listar_premisas import listar_premisas
from .handlers.listar_sesiones import mis_sesiones, sesiones_publicadas
from .handlers.mi_perfil import build_editar_perfil_handler, ver_perfil
from .handlers.perfil_dm import (
    abrir_editar_dm,
    abrir_picker_juegos,
    abrir_picker_premisas,
    add_juego,
    add_premisa,
    build_crear_dm_handler,
    build_editar_dm_bio_handler,
    picker_done,
    ver_dm_juegos,
    ver_dm_premisas,
    ver_perfil_dm,
)
from .handlers.proximamente import proximamente
from .handlers.start import start
from .handlers.suscripciones import (
    desuscribirme,
    dm_suscriptores,
    mis_suscripciones,
    toggle_suscripcion,
)
from .handlers.unirse import build_handler as build_unirse
from .keyboards import CAJAS

# Comandos sugeridos en el menú nativo de Telegram (pulsa "/" en el chat).
# Se incluyen los que aún no están implementados con etiqueta "(próx.)" para
# no rehacer set_my_commands cada fase. Los handlers que falten responden
# "🚧 Próximamente" via el catch-all proximamente.
BOT_COMMANDS: list[BotCommand] = [
    # Vacío a propósito: el menú nativo de "/" en el cliente no debe
    # mostrar nada. La interacción habitual va por el mensaje fijado en
    # el DM (botones inline ❓ Ayuda / 🏠 Inicio, ver `bot/menu_dm.py`)
    # y por las cajas del ReplyKeyboard. Los comandos siguen funcionando
    # si se teclean a mano: `/start`, `/help`, `/cancelar`,
    # `/rotar_token`, `/publicar_pin`.
]


async def post_initialize(application: Application) -> None:
    """Inicializaciones que requieren un bot ya inicializado.

    - Publica los BotCommands en el menú nativo.
    - Cachea el username del bot para construir deep-link URLs.
    - Importa los formatters de object_links (auto-registro on import).

    Llamar explícitamente desde el entrypoint tras `application.initialize()`.
    No se registra como `post_init` del builder porque PTB solo invoca ese
    hook desde `run_polling()`/`run_webhook()`, y nuestros entrypoints
    (FastAPI lifespan, devbot) hacen el ciclo de vida a mano.
    """
    import logging

    # Comandos visibles SOLO en chats privados. En grupos / hilos / al
    # listar como admin de grupo, vaciamos explícitamente para sobrescribir
    # cualquier set_my_commands previo (Telegram persiste el último valor
    # de cada scope hasta que se reemplaza). Limpiar también el scope
    # Default cubre clientes antiguos que no implementan los scopes
    # específicos y caerían en el fallback.
    await application.bot.set_my_commands(
        BOT_COMMANDS, scope=BotCommandScopeAllPrivateChats()
    )
    await application.bot.set_my_commands(
        [], scope=BotCommandScopeAllGroupChats()
    )
    await application.bot.set_my_commands(
        [], scope=BotCommandScopeAllChatAdministrators()
    )
    await application.bot.set_my_commands(
        [], scope=BotCommandScopeDefault()
    )

    # Importa para registrar formatters (premisa, juego, dm, sesion).
    from . import object_formatters  # noqa: F401
    from .object_links import set_bot_username

    me = await application.bot.get_me()
    set_bot_username(me.username)
    logging.getLogger("tmjr").warning(
        "Bot username cacheado: @%s (deep-links activados)", me.username
    )


def _register_handlers(application: Application) -> None:
    # Política: el bot solo responde a comandos en chats privados. En grupos
    # o canales los CommandHandler quedan filtrados (no responde nada). Lo
    # único que aparece en el canal son las tarjetas de sesión publicadas
    # explícitamente desde `publicar_sesion`.
    only_private = filters.ChatType.PRIVATE

    # Comandos directos (solo en privado).
    logging.warning("Registrando handler de /start")
    application.add_handler(CommandHandler("start", start, filters=only_private))
    logging.warning("Handler de /start registrado")
    application.add_handler(CommandHandler("help", help_command, filters=only_private))
    application.add_handler(
        CommandHandler("listar_sesiones", sesiones_publicadas, filters=only_private)
    )
    application.add_handler(
        CommandHandler("listar_juegos", listar_juegos, filters=only_private)
    )
    application.add_handler(
        CommandHandler("listar_premisas", listar_premisas, filters=only_private)
    )
    application.add_handler(
        CommandHandler("mi_perfil", ver_perfil, filters=only_private)
    )
    # Comandos admin (whitelist en ADMIN_TELEGRAM_IDS).
    application.add_handler(
        CommandHandler("rotar_token", rotar_token, filters=only_private)
    )
    application.add_handler(
        CommandHandler("publicar_pin", publicar_pin, filters=only_private)
    )
    # Las campañas se gestionan vía la caja, no hay /crear_campania ni
    # /listar_campanias directos por ahora.

    # ConversationHandlers (deben ir antes del MessageHandler de cajas para
    # que sus filters.TEXT capturen primero los mensajes durante un flujo).
    # También antes del catch-all `caja_*` de proximamente, para que los
    # callbacks `caja_*` los absorban antes que el stub de "próximamente".
    application.add_handler(build_crear_sesion())
    application.add_handler(build_crear_premisa())
    application.add_handler(build_editar_sesion())
    application.add_handler(build_editar_premisa())
    application.add_handler(build_gestionar_campania())
    application.add_handler(build_editar_perfil_handler())
    application.add_handler(build_crear_dm_handler())
    application.add_handler(build_editar_dm_bio_handler())
    application.add_handler(build_unirse())
    # Borrarse de una sesión (one-shot, sin conversación).
    application.add_handler(
        CallbackQueryHandler(desapuntarse, pattern=r"^desapuntar_\d+$")
    )
    # +1 / -1 de invitados sin Telegram.
    application.add_handler(CallbackQueryHandler(mas1, pattern=r"^mas1_\d+$"))
    application.add_handler(CallbackQueryHandler(menos1, pattern=r"^menos1_\d+$"))

    # Botones del mensaje fijado del DM (menú principal).
    async def _menu_help(update, context):
        if update.callback_query is not None:
            await update.callback_query.answer()
        await help_command(update, context)

    async def _menu_start(update, context):
        if update.callback_query is not None:
            await update.callback_query.answer()
        await start(update, context)

    application.add_handler(CallbackQueryHandler(_menu_help, pattern=r"^menu_help$"))
    application.add_handler(CallbackQueryHandler(_menu_start, pattern=r"^menu_start$"))

    # Callbacks de los submenús inline.
    application.add_handler(
        CallbackQueryHandler(ver_perfil, pattern=r"^caja_persona_ver$")
    )
    # Perfil DM: ver/editar y pickers de juegos/premisas.
    application.add_handler(
        CallbackQueryHandler(ver_perfil_dm, pattern=r"^caja_persona_ver_dm$")
    )
    application.add_handler(
        CallbackQueryHandler(
            ver_dm_premisas, pattern=r"^caja_persona_ver_dm_premisas$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            ver_dm_juegos, pattern=r"^caja_persona_ver_dm_juegos$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            dm_suscriptores, pattern=r"^caja_persona_ver_dm_suscriptores$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(abrir_editar_dm, pattern=r"^caja_persona_editar_dm$")
    )
    application.add_handler(
        CallbackQueryHandler(
            abrir_picker_juegos, pattern=r"^caja_persona_editar_dm_juego$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            abrir_picker_premisas, pattern=r"^caja_persona_editar_dm_premisa$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(add_juego, pattern=r"^dm_add_juego_\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(add_premisa, pattern=r"^dm_add_premisa_\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(picker_done, pattern=r"^dm_picker_done$")
    )

    application.add_handler(
        CallbackQueryHandler(mis_sesiones, pattern=r"^caja_sesion_mis$")
    )
    application.add_handler(
        CallbackQueryHandler(
            sesiones_publicadas, pattern=r"^caja_sesion_publicadas$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(listar_juegos, pattern=r"^caja_juegos_listar$")
    )
    application.add_handler(
        CallbackQueryHandler(listar_premisas, pattern=r"^caja_premisa_listar$")
    )
    # Suscripciones a premisas.
    application.add_handler(
        CallbackQueryHandler(
            mis_suscripciones, pattern=r"^caja_persona_suscripciones$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(toggle_suscripcion, pattern=r"^prem_suscr_\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(desuscribirme, pattern=r"^prem_desuscr_\d+$")
    )
    # Caja Campaña → Info (one-shot). Crear y Listar los absorben los
    # ConversationHandlers ya registrados arriba.
    application.add_handler(
        CallbackQueryHandler(info_campania, pattern=r"^caja_campania_info$")
    )
    # Catch-all para los caja_*_* aún no implementados (Premisa/Listar/Editar,
    # Campania/*, Juegos/{Crear,Editar}, Sesion/Editar).
    # Ojo: los caja_persona_* y caja_sesion_crear ya los absorben los handlers
    # registrados arriba.
    application.add_handler(CallbackQueryHandler(proximamente, pattern=r"^caja_"))

    # Cajas del ReplyKeyboard: el usuario pulsa "👤 Persona", llega como texto.
    # Solo en privado para que un texto suelto en grupo no dispare nada.
    cajas_regex = r"^(" + "|".join(CAJAS) + r")$"
    application.add_handler(
        MessageHandler(
            filters.Regex(cajas_regex) & only_private, caja_dispatcher
        )
    )


def build_application(*, polling: bool = False) -> Application:
    settings = get_settings()
    builder = Application.builder().token(settings.telegram_token)
    if not polling:
        builder = builder.updater(None)  # webhook: no polling
    application = builder.build()
    _register_handlers(application)
    return application