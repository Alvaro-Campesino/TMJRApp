"""Fixtures de la suite e2e.

- Postgres ephemero (testcontainers) por sesión de pytest.
- Settings y engine reseteados antes del lifespan de FastAPI.
- LifespanManager para arrancar PTB de verdad (mockeando la API de Telegram con respx).
- Aislamiento por test: tras cada test, vaciamos todas las tablas.
"""
from __future__ import annotations

import os
from typing import AsyncIterator

import httpx
import pytest
import pytest_asyncio
import respx
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

# IMPORTANTE: estos imports cachean Settings() con el .env de turno; los reseteamos
# en `_e2e_environment` antes de que el lifespan los use.
from tmjr.config import get_settings
from tmjr.db import models  # noqa: F401 — registra los modelos en Base.metadata
from tmjr.db.session import Base
from tmjr.db import reset_db_state

E2E_TOKEN = "1234567890:dummy-e2e"
E2E_CHAT_ID = "-1001234567890"
E2E_BOT_USERNAME = "tmjr_e2e_bot"


# ───────────────────────── Postgres por sesión ─────────────────────────


@pytest.fixture(scope="session")
def postgres_container():
    """Levanta un postgres:16-alpine con driver asyncpg y lo apaga al final."""
    pg = PostgresContainer(
        "postgres:16-alpine",
        username="tmjr",
        password="tmjr",
        dbname="tmjr",
        driver="asyncpg",
    )
    pg.start()
    try:
        yield pg
    finally:
        pg.stop()


@pytest.fixture(scope="session")
def database_url(postgres_container) -> str:
    return postgres_container.get_connection_url()


# ───────────────────────── Variables de entorno ────────────────────────


@pytest.fixture(scope="session")
def _e2e_environment(database_url):
    """Reescribe env vars para que apunten al postgres y a un bot mockeado.

    Limpia la caché de get_settings y resetea el engine antes de que ningún
    test toque la app.
    """
    saved = {}
    overrides = {
        "DATABASE_URL": database_url,
        "TELEGRAM_TOKEN": E2E_TOKEN,
        "TELEGRAM_CHAT_ID": E2E_CHAT_ID,
        "TELEGRAM_THREAD_ID": "",
        "TELEGRAM_WEBHOOK_URL": "",
        "TELEGRAM_WEBHOOK_SECRET": "",
    }
    for k, v in overrides.items():
        saved[k] = os.environ.get(k)
        os.environ[k] = v

    get_settings.cache_clear()

    yield

    for k, original in saved.items():
        if original is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = original
    get_settings.cache_clear()


# ───────────────────────── Schema de la DB ─────────────────────────────


@pytest_asyncio.fixture(scope="session")
async def _setup_schema(_e2e_environment, database_url):
    """Crea todas las tablas en la DB de test."""
    eng = create_async_engine(database_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(_setup_schema, database_url) -> AsyncIterator[AsyncSession]:
    """Sesión de test contra la DB e2e. Trunca todas las tablas al final."""
    eng = create_async_engine(database_url)
    sm = async_sessionmaker(eng, expire_on_commit=False, class_=AsyncSession)
    async with sm() as session:
        yield session
    # Limpia para el siguiente test
    async with eng.begin() as conn:
        for t in reversed(Base.metadata.sorted_tables):
            await conn.execute(t.delete())
    await eng.dispose()


# ───────────────────────── Mock de la API de Telegram ──────────────────


@pytest_asyncio.fixture
async def telegram_mock():
    """Intercepta TODAS las llamadas a api.telegram.org.

    Defaults razonables para los métodos que el bot usa en este MVP:
    `getMe`, `sendMessage`, `answerCallbackQuery`, `setWebhook`, `deleteWebhook`.
    """
    base = "https://api.telegram.org"
    bot_path = f"/bot{E2E_TOKEN}"

    with respx.mock(assert_all_called=False) as r:
        r.post(f"{base}{bot_path}/getMe").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "id": int(E2E_TOKEN.split(":")[0]),
                        "is_bot": True,
                        "first_name": "tmjr-e2e",
                        "username": E2E_BOT_USERNAME,
                        "can_join_groups": True,
                        "can_read_all_group_messages": False,
                        "supports_inline_queries": False,
                    },
                },
            )
        )
        r.post(f"{base}{bot_path}/sendMessage").mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "message_id": 999,
                        "date": 0,
                        "chat": {"id": 999, "type": "private", "first_name": "T"},
                        "text": "ok",
                    },
                },
            )
        )
        r.post(f"{base}{bot_path}/answerCallbackQuery").mock(
            return_value=Response(200, json={"ok": True, "result": True})
        )
        r.post(f"{base}{bot_path}/setWebhook").mock(
            return_value=Response(200, json={"ok": True, "result": True})
        )
        r.post(f"{base}{bot_path}/deleteWebhook").mock(
            return_value=Response(200, json={"ok": True, "result": True})
        )
        # Catch-all por si PTB hace cualquier otra llamada (getUpdates, getMyCommands, etc.)
        r.route(host="api.telegram.org").mock(
            return_value=Response(200, json={"ok": True, "result": True})
        )
        yield r


# ─────────────────────── App con lifespan + cliente ────────────────────


@pytest_asyncio.fixture
async def app(_setup_schema, telegram_mock):
    """Devuelve la FastAPI app con su lifespan completo (PTB inicializado)."""
    # Resetea cualquier engine/sessionmaker creado por tests anteriores.
    await reset_db_state()
    get_settings.cache_clear()

    # Importamos dentro de la fixture para que el lifespan use los settings frescos.
    from tmjr.main import app as fastapi_app

    async with LifespanManager(fastapi_app) as manager:
        yield manager.app

    await reset_db_state()


@pytest_asyncio.fixture
async def http_client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


# ─────────────────────── Helpers para construir Updates ─────────────────


@pytest.fixture
def make_text_update():
    """Devuelve un constructor de Updates de tipo `message` con texto."""
    counter = {"n": 0}

    def _build(*, telegram_id: int, text: str, first_name: str = "Test"):
        counter["n"] += 1
        message: dict = {
            "message_id": 100 + counter["n"],
            "from": {
                "id": telegram_id,
                "is_bot": False,
                "first_name": first_name,
                "language_code": "es",
            },
            "chat": {
                "id": telegram_id,
                "type": "private",
                "first_name": first_name,
            },
            "date": 1700000000 + counter["n"],
            "text": text,
        }
        # CommandHandler exige una entity `bot_command` para reconocer "/cmd".
        if text.startswith("/"):
            cmd = text.split()[0]
            message["entities"] = [
                {"type": "bot_command", "offset": 0, "length": len(cmd)}
            ]
        return {"update_id": counter["n"], "message": message}

    return _build


@pytest.fixture
def make_callback_update():
    """Devuelve un constructor de Updates de tipo `callback_query`.

    Por defecto el callback viene del chat privado del usuario (donde aparece
    el menú principal). Para callbacks desde la tarjeta del canal, pasa
    `from_channel=True`.
    """
    counter = {"n": 0}

    def _build(
        *,
        telegram_id: int,
        data: str,
        first_name: str = "Test",
        from_channel: bool = False,
    ):
        counter["n"] += 1
        if from_channel:
            chat = {"id": int(E2E_CHAT_ID), "type": "supergroup", "title": "canal"}
        else:
            chat = {"id": telegram_id, "type": "private", "first_name": first_name}

        return {
            "update_id": 5000 + counter["n"],
            "callback_query": {
                "id": str(counter["n"]),
                "from": {
                    "id": telegram_id,
                    "is_bot": False,
                    "first_name": first_name,
                    "language_code": "es",
                },
                "message": {
                    "message_id": 200 + counter["n"],
                    "from": {
                        "id": int(E2E_TOKEN.split(":")[0]),
                        "is_bot": True,
                        "first_name": "tmjr-e2e",
                        "username": E2E_BOT_USERNAME,
                    },
                    "chat": chat,
                    "date": 1700000000 + counter["n"],
                    "text": "Sesión",
                },
                "chat_instance": "x",
                "data": data,
            },
        }

    return _build


# ─────────────────── Marker auto-aplicado a esta suite ──────────────────


def pytest_collection_modifyitems(config, items):
    """Marca todos los tests de tests/e2e/ con @pytest.mark.e2e automáticamente."""
    for item in items:
        if "tests/e2e/" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
