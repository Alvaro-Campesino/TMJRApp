"""Tests sobre el módulo de teclados inline. Sin DB ni red."""
from __future__ import annotations

from telegram import InlineKeyboardMarkup

from tmjr.bot import keyboards


def test_menu_principal_tiene_dos_botones():
    kb = keyboards.menu_principal()
    assert isinstance(kb, InlineKeyboardMarkup)
    botones = [b for fila in kb.inline_keyboard for b in fila]
    callbacks = {b.callback_data for b in botones}
    assert callbacks == {"crear_sesion", "unirse_sesion"}


def test_tarjeta_sesion_callback_codifica_id():
    kb = keyboards.tarjeta_sesion(42)
    boton = kb.inline_keyboard[0][0]
    assert boton.callback_data == "apuntar_42"


def test_confirmar_cancelar_genera_callbacks_con_prefix():
    kb = keyboards.confirmar_cancelar("crear")
    fila = kb.inline_keyboard[0]
    assert {b.callback_data for b in fila} == {"crear_ok", "crear_no"}
