"""Tests sobre el módulo de teclados inline. Sin DB ni red."""
from __future__ import annotations

from datetime import date

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup

from tmjr.bot import keyboards


def test_menu_cajas_contiene_las_cinco_cajas():
    kb = keyboards.menu_cajas()
    assert isinstance(kb, ReplyKeyboardMarkup)
    labels = {b.text for fila in kb.keyboard for b in fila}
    assert labels == set(keyboards.CAJAS)


def test_tarjeta_sesion_callback_codifica_id():
    kb = keyboards.tarjeta_sesion(42)
    boton = kb.inline_keyboard[0][0]
    assert boton.callback_data == "apuntar_42"


def test_confirmar_cancelar_genera_callbacks_con_prefix():
    kb = keyboards.confirmar_cancelar("crear")
    fila = kb.inline_keyboard[0]
    assert {b.callback_data for b in fila} == {"crear_ok", "crear_no"}


def test_calendario_grid_basica():
    kb = keyboards.calendario(2026, 5, min_date=None)
    rows = kb.inline_keyboard

    # Cabecera + nombres de día + 5 o 6 semanas
    assert 7 <= len(rows) <= 8

    # Cabecera: ‹ navega al mes anterior, › al siguiente, centro es noop
    assert rows[0][0].callback_data == "cal_nav_2026-04"
    assert rows[0][1].callback_data == "cal_noop"
    assert "Mayo 2026" in rows[0][1].text
    assert rows[0][2].callback_data == "cal_nav_2026-06"

    # Nombres de día empiezan en lunes
    assert [b.text for b in rows[1]] == ["L", "M", "X", "J", "V", "S", "D"]

    # Día 15 es seleccionable
    callbacks = {b.callback_data for fila in rows[2:] for b in fila}
    assert "cal_pick_2026-05-15" in callbacks


def test_calendario_min_date_deshabilita_pasado_y_back():
    kb = keyboards.calendario(2026, 5, min_date=date(2026, 5, 10))
    rows = kb.inline_keyboard

    # El último día del mes anterior (2026-04-30) es < 2026-05-10, así que la
    # flecha ‹ debe quedar deshabilitada.
    assert rows[0][0].callback_data == "cal_noop"

    # Días previos al min_date no son seleccionables; el min_date sí lo es.
    callbacks = {b.callback_data for fila in rows[2:] for b in fila}
    assert "cal_pick_2026-05-01" not in callbacks
    assert "cal_pick_2026-05-09" not in callbacks
    assert "cal_pick_2026-05-10" in callbacks


def test_calendario_cambio_de_anio_en_navegacion():
    kb = keyboards.calendario(2026, 12, min_date=None)
    rows = kb.inline_keyboard
    assert rows[0][0].callback_data == "cal_nav_2026-11"
    assert rows[0][2].callback_data == "cal_nav_2027-01"

    kb = keyboards.calendario(2026, 1, min_date=None)
    rows = kb.inline_keyboard
    assert rows[0][0].callback_data == "cal_nav_2025-12"
    assert rows[0][2].callback_data == "cal_nav_2026-02"


# ─────────────────────── caja Persona dinámico ────────────────────


def _callbacks(kb: InlineKeyboardMarkup) -> set[str]:
    return {b.callback_data for fila in kb.inline_keyboard for b in fila}


def test_submenu_persona_no_dm_ofrece_crear_dm():
    kb = keyboards.submenu_persona(es_dm=False)
    cbs = _callbacks(kb)
    assert "caja_persona_ver" in cbs
    assert "caja_persona_editar" in cbs
    assert "caja_persona_crear_dm" in cbs
    assert "caja_persona_ver_dm" not in cbs
    assert "caja_persona_editar_dm" not in cbs


def test_submenu_persona_dm_ofrece_ver_y_editar_dm():
    kb = keyboards.submenu_persona(es_dm=True)
    cbs = _callbacks(kb)
    assert "caja_persona_ver" in cbs
    assert "caja_persona_editar" in cbs
    assert "caja_persona_ver_dm" in cbs
    assert "caja_persona_editar_dm" in cbs
    assert "caja_persona_crear_dm" not in cbs


def test_submenu_editar_dm_tiene_tres_acciones():
    kb = keyboards.submenu_editar_dm()
    cbs = _callbacks(kb)
    assert cbs == {
        "caja_persona_editar_dm_bio",
        "caja_persona_editar_dm_juego",
        "caja_persona_editar_dm_premisa",
    }


def test_vista_perfil_dm_tiene_botones_de_listado():
    kb = keyboards.vista_perfil_dm()
    cbs = _callbacks(kb)
    assert cbs == {
        "caja_persona_ver_dm_juegos",
        "caja_persona_ver_dm_premisas",
    }


# ─────────────────────── pickers DM ───────────────────────────────


def test_picker_juegos_codifica_id_y_anade_hecho():
    kb = keyboards.picker_juegos_para_dm([(7, "D&D 5e"), (12, "Vampiro")])
    cbs = _callbacks(kb)
    assert "dm_add_juego_7" in cbs
    assert "dm_add_juego_12" in cbs
    assert "dm_picker_done" in cbs


def test_picker_juegos_vacio_solo_tiene_hecho():
    kb = keyboards.picker_juegos_para_dm([])
    cbs = _callbacks(kb)
    assert cbs == {"dm_picker_done"}


def test_picker_premisas_codifica_id_y_anade_hecho():
    kb = keyboards.picker_premisas_para_dm([(3, "Strahd"), (4, "Doskvol")])
    cbs = _callbacks(kb)
    assert "dm_add_premisa_3" in cbs
    assert "dm_add_premisa_4" in cbs
    assert "dm_picker_done" in cbs
