"""Tests del publicador de sesiones con un Bot mockeado."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from tmjr.bot import publicador
from tmjr.config import get_settings
from tmjr.db.models import Sesion


def _sesion_demo() -> Sesion:
    return Sesion(
        id=1,
        id_dm=10,
        fecha=date(2030, 4, 4),
        plazas_totales=4,
        plazas_sin_reserva=1,
    )


async def test_publicar_sesion_falla_sin_chat_id(monkeypatch):
    get_settings.cache_clear()
    # Set explícito a vacío: el validador lo convierte a None
    # (delenv no basta porque pydantic-settings también lee del .env del repo).
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    bot = MagicMock()

    with pytest.raises(RuntimeError, match="TELEGRAM_CHAT_ID"):
        await publicador.publicar_sesion(bot, _sesion_demo())

    get_settings.cache_clear()


async def test_publicar_sesion_envia_mensaje(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001234567890")
    monkeypatch.setenv("TELEGRAM_THREAD_ID", "7")

    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))

    chat_id, thread_id, message_id = await publicador.publicar_sesion(
        bot, _sesion_demo()
    )

    assert chat_id == "-1001234567890"
    assert thread_id == 7
    assert message_id == 999

    bot.send_message.assert_awaited_once()
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == "-1001234567890"
    assert kwargs["message_thread_id"] == 7
    assert "Sesión #1" in kwargs["text"]
    assert "2030-04-04" in kwargs["text"]

    get_settings.cache_clear()
