"""Entrypoint de DESARROLLO: bot en polling.

Arranca:
    .venv/bin/python -m tmjr.devbot

Diferencias con `tmjr.main` (producción):
- NO arranca FastAPI ni el endpoint /telegram/webhook.
- NO necesita TELEGRAM_WEBHOOK_URL ni cert; pulla updates con `getUpdates`.
- Llama a `delete_webhook(drop_pending_updates=False)` antes de empezar
  porque Telegram no permite webhook + polling al mismo tiempo. Si tu bot
  estaba con webhook configurado (p.ej. el desplegado en QNAP), se desactiva.
- Usa los MISMOS handlers que producción → cualquier breakpoint que pongas
  en bot/handlers/* se dispara igual cuando interactúas en Telegram.

Recomendado para dev: tener un bot SEPARADO en BotFather (@xxx_dev_bot) con
su propio token, para no pisar el webhook del bot de prod.
"""
from __future__ import annotations

import asyncio
import logging
import signal

from tmjr.bot.app import build_application, post_initialize
from tmjr.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tmjr.devbot")


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_token:
        raise RuntimeError("TELEGRAM_TOKEN no está en .env")

    application = build_application(polling=True)
    await application.initialize()
    await post_initialize(application)

    # Polling exige no tener webhook activo.
    me = await application.bot.get_me()
    info = await application.bot.get_webhook_info()
    if info.url:
        logger.warning(
            "Bot @%s tenía webhook en %s — lo borro para arrancar polling.",
            me.username, info.url,
        )
        await application.bot.delete_webhook(drop_pending_updates=False)

    logger.warning("✓ Bot @%s en polling. Ctrl+C para parar.", me.username)

    await application.start()
    await application.updater.start_polling()

    # Espera bloqueante hasta SIGINT / SIGTERM
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()

    logger.warning("→ Parando…")
    await application.updater.stop()
    await application.stop()
    await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
