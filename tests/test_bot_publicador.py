"""Tests del publicador de sesiones con un Bot mockeado."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from tmjr.bot import publicador
from tmjr.bot.publicador import _formatear
from tmjr.config import get_settings
from tmjr.db.models import Premisa, Sesion


def _sesion_demo(descripcion: str | None = None) -> Sesion:
    return Sesion(
        id=1,
        id_dm=10,
        id_juego=1,
        fecha=date(2030, 4, 4),
        plazas_totales=4,
        plazas_sin_reserva=1,
        descripcion=descripcion,
    )


def _premisa_demo(descripcion: str | None = None) -> Premisa:
    return Premisa(id=1, nombre="Maldición de Strahd", descripcion=descripcion)


def test_formatear_sesion_sola_sin_descripcion():
    txt = _formatear(_sesion_demo())
    assert "Sesión #1" in txt
    assert "📅 2030-04-04" in txt
    # No hay línea de descripción
    assert "_" not in txt or txt.count("_") == 0


def test_formatear_usa_descripcion_de_premisa_si_sesion_sin():
    txt = _formatear(_sesion_demo(), _premisa_demo("Aventura clásica"))
    assert "Maldición de Strahd" in txt
    assert "Aventura clásica" in txt


def test_formatear_descripcion_de_sesion_sobreescribe_premisa():
    txt = _formatear(
        _sesion_demo("Nota específica de hoy"),
        _premisa_demo("Aventura clásica"),
    )
    assert "Nota específica de hoy" in txt
    assert "Aventura clásica" not in txt


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
