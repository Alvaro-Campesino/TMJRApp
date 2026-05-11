"""Entrypoint: FastAPI + PTB en un solo proceso.

Arranca con: `uvicorn tmjr.main:app --host 0.0.0.0 --port 80`
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, Header, HTTPException, Request, status
from telegram import Update
from telegram.error import TelegramError

from tmjr.api.juegos import router as juegos_router
from tmjr.api.personas import router as personas_router
from tmjr.api.sesiones import router as sesiones_router
from tmjr.bot.app import build_application, post_initialize
from tmjr.config import get_settings

# Asegura que los logs propios (no solo los de uvicorn) salgan por stdout.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tmjr")


_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _run_alembic_upgrade() -> None:
    """Aplica `alembic upgrade head` usando alembic.ini del repo.

    Síncrono: pensado para invocarse desde el lifespan vía `asyncio.to_thread`.
    Si no encuentra el fichero de config (p.ej. arranque desde un CWD raro
    sin el repo entero), loguea y no aborta — el operador puede aplicar
    las migraciones a mano.
    """
    if not _ALEMBIC_INI.is_file():
        logger.error(
            "alembic.ini no encontrado en %s — saltando migraciones automáticas. "
            "Aplica `alembic upgrade head` a mano.",
            _ALEMBIC_INI,
        )
        return
    cfg = AlembicConfig(str(_ALEMBIC_INI))
    alembic_command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.ptb = None

    logger.warning(
        "Lifespan: token=%s url=%s cert_file=%s chat=%s",
        "set" if settings.telegram_token else "EMPTY",
        settings.telegram_webhook_url or "EMPTY",
        settings.telegram_webhook_cert_file or "EMPTY",
        settings.telegram_chat_id or "EMPTY",
    )

    logger.warning("Aplicando migraciones de Alembic (upgrade head)...")
    try:
        await asyncio.to_thread(_run_alembic_upgrade)
        logger.warning("Migraciones aplicadas.")
    except Exception as exc:
        # No tiramos la app: si las migraciones fallan, el operador querrá
        # ver el log y resolverlo (p.ej. permisos de DB, conflicto de heads).
        logger.error("Fallo aplicando migraciones: %s", exc)

    if not settings.telegram_token:
        # Modo API-only: útil para correr tests sin necesidad de Telegram.
        logger.warning("TELEGRAM_TOKEN vacío → modo API-only, bot no arranca.")
        yield
        return

    application = build_application()
    await application.initialize()
    await post_initialize(application)
    await application.start()

    if settings.telegram_webhook_url:
        cert_kwarg = {}
        if settings.telegram_webhook_cert_file:
            cert_path = Path(settings.telegram_webhook_cert_file)
            if cert_path.is_file():
                cert_kwarg["certificate"] = cert_path
                logger.warning("Subiendo cert self-signed: %s", cert_path)
            else:
                # CRÍTICO: si nos piden cert pero no lo encontramos, NO tocamos
                # el webhook. Si lo tocásemos sin cert, machacaríamos un webhook
                # bueno (con cert subido manualmente) y romperíamos producción.
                # Mejor dejar la config tal cual está y avisar.
                logger.error(
                    "TELEGRAM_WEBHOOK_CERT_FILE=%s NO existe en el contenedor. "
                    "NO toco setWebhook para no machacar la config actual. "
                    "Sube el cert al host y reinicia, o desactiva la variable.",
                    cert_path,
                )
                app.state.ptb = application
                try:
                    yield
                finally:
                    await application.stop()
                    await application.shutdown()
                return

        try:
            await application.bot.set_webhook(
                url=settings.telegram_webhook_url,
                secret_token=settings.telegram_webhook_secret,
                allowed_updates=Update.ALL_TYPES,
                **cert_kwarg,
            )
            logger.warning("Webhook registrado en %s", settings.telegram_webhook_url)
        except TelegramError as exc:
            # No tiramos la app si Telegram rechaza el setWebhook (URL no resuelve,
            # cert no válido, secret mal, etc.). El bot sigue arrancando; al
            # arreglar la URL/cert, basta reiniciar.
            logger.error(
                "set_webhook falló (%s). El bot arranca igual; "
                "reintenta `setWebhook` cuando la URL/cert estén OK.", exc,
            )

    app.state.ptb = application
    try:
        yield
    finally:
        await application.stop()
        await application.shutdown()


app = FastAPI(title="TMJRApp", lifespan=lifespan)
app.include_router(personas_router)
app.include_router(sesiones_router)
app.include_router(juegos_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    settings = get_settings()
    if settings.telegram_webhook_secret and (
        x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    application = request.app.state.ptb
    if application is None:
        raise HTTPException(status_code=503, detail="Bot no configurado")

    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}
