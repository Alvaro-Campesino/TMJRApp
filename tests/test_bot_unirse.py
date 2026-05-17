"""Tests del handler `unirse`.

Por ahora solo cubre el helper puro de construcción del enlace al
mensaje publicado en el canal — el flujo entero del ConversationHandler
está cubierto por la suite e2e (opt-in con docker).
"""
from __future__ import annotations

from datetime import datetime

from tmjr.bot.handlers.unirse import _link_a_mensaje_publicado
from tmjr.db.models import Sesion


def _sesion(
    *,
    chat_id: str | None = "-1001234567890",
    thread_id: int | None = None,
    message_id: int | None = 42,
) -> Sesion:
    return Sesion(
        id=1,
        id_dm=1,
        id_juego=1,
        fecha=datetime(2030, 1, 1, 18, 30),
        plazas_totales=4,
        plazas_sin_reserva=1,
        telegram_chat_id=chat_id,
        telegram_thread_id=thread_id,
        telegram_message_id=message_id,
    )


def test_link_a_mensaje_publicado_supergroup_sin_thread():
    s = _sesion()
    assert (
        _link_a_mensaje_publicado(s)
        == "https://t.me/c/1234567890/42"
    )


def test_link_a_mensaje_publicado_con_thread():
    s = _sesion(thread_id=7)
    assert (
        _link_a_mensaje_publicado(s)
        == "https://t.me/c/1234567890/7/42"
    )


def test_link_a_mensaje_publicado_sin_message_id():
    s = _sesion(message_id=None)
    assert _link_a_mensaje_publicado(s) is None


def test_link_a_mensaje_publicado_sin_chat_id():
    s = _sesion(chat_id=None)
    assert _link_a_mensaje_publicado(s) is None


def test_link_a_mensaje_publicado_chat_no_es_canal_supergroup():
    """Chats privados / grupos clásicos (sin prefijo -100) no son enlazables."""
    s = _sesion(chat_id="-12345")
    assert _link_a_mensaje_publicado(s) is None
