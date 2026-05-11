"""End-to-end de los flujos del bot:

- /start crea persona en BD y manda saludo.
- Crear sesión: persona sin DM → bot pide bio → fecha (calendario) → plazas → crea sesión y publica tarjeta.
- Unirse a sesión: persona sin PJ pulsa botón → bot pide nombre/desc del PJ → apunta.

La API HTTP de Telegram está mockeada con respx; la BD es Postgres ephemero.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from tests.e2e.conftest import E2E_CHAT_ID, E2E_TOKEN
from tmjr.db.models import DM, PJ, Juego, Persona, Premisa, Sesion, SesionPJ


def _target_fecha(days_offset: int = 60) -> date:
    """Una fecha futura suficientemente lejos para no estar en el mes actual."""
    return date.today() + timedelta(days=days_offset)


def _cal_pick(d: date) -> str:
    return f"cal_pick_{d.year:04d}-{d.month:02d}-{d.day:02d}"


def _cal_nav(d: date) -> str:
    return f"cal_nav_{d.year:04d}-{d.month:02d}"


def _send_message_calls(telegram_mock):
    return [
        c for c in telegram_mock.calls
        if c.request.url.path.endswith("/sendMessage")
    ]


def _payload(call) -> dict:
    """Decodifica el body (JSON o form-urlencoded) de una llamada."""
    body = call.request.read()
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        from urllib.parse import parse_qs
        parsed = parse_qs(body.decode())
        return {k: v[0] for k, v in parsed.items()}


# ───────────────────────── /start ─────────────────────────


async def test_start_crea_persona_en_db(http_client, telegram_mock, db_session, make_text_update):
    update = make_text_update(telegram_id=10001, text="/start", first_name="Alvaro")
    r = await http_client.post("/telegram/webhook", json=update)
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    persona = (
        await db_session.execute(select(Persona).where(Persona.telegram_id == 10001))
    ).scalar_one_or_none()
    assert persona is not None
    assert persona.nombre == "Alvaro"
    assert persona.id_master is None
    assert persona.id_pj is None


async def test_start_responde_con_saludo(http_client, telegram_mock, make_text_update):
    update = make_text_update(telegram_id=10002, text="/start", first_name="Hola")
    await http_client.post("/telegram/webhook", json=update)

    calls = _send_message_calls(telegram_mock)
    assert len(calls) >= 1
    payload = _payload(calls[-1])
    assert "Hola" in payload["text"]
    assert "registrado" in payload["text"].lower()


async def test_start_idempotente(http_client, telegram_mock, db_session, make_text_update):
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=10003, text="/start"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=10003, text="/start"),
    )

    rows = (
        await db_session.execute(select(Persona).where(Persona.telegram_id == 10003))
    ).scalars().all()
    assert len(rows) == 1


# ──────────────────────── Crear sesión ────────────────────────


async def test_crear_sesion_full_flow_crea_dm_premisa_juego_y_publica(
    http_client, telegram_mock, db_session, make_text_update, make_callback_update
):
    tg_id = 20001

    # 1. /start
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="/start", first_name="DM-Test"),
    )
    # 2. Pulsa "Crear sesión"
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data="crear_sesion"),
    )
    # 3. Bio (DM nuevo)
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="DM con 5 años de experiencia"),
    )
    # 4. Nombre de la premisa
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="La maldición de Strahd"),
    )
    # 5. Descripción
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="Aventura clásica de Ravenloft"),
    )
    # 6. Lista de juegos vacía → pulsa "Añadir nuevo"
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data="juego_nuevo"),
    )
    # 7. Nombre del juego nuevo (no existe en catálogo)
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="D&D 5e"),
    )
    # 8. Confirma crearlo en catálogo
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data="nuevo_juego_ok"),
    )
    # 9. Fecha — navega al mes objetivo y selecciona el día
    target = _target_fecha()
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data=_cal_nav(target)),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data=_cal_pick(target)),
    )
    # 10. Plazas
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="4"),
    )
    # 11. Nota específica de esta sesión
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="Nivel 5, traer copia"),
    )

    # ─── Comprobaciones ───
    persona = (
        await db_session.execute(select(Persona).where(Persona.telegram_id == tg_id))
    ).scalar_one()
    assert persona.id_master is not None

    juegos = (await db_session.execute(select(Juego))).scalars().all()
    assert [j.nombre for j in juegos] == ["D&D 5e"]

    premisas = (await db_session.execute(select(Premisa))).scalars().all()
    assert len(premisas) == 1
    p = premisas[0]
    assert p.nombre == "La maldición de Strahd"
    assert p.descripcion == "Aventura clásica de Ravenloft"
    assert p.id_juego == juegos[0].id

    sesiones = (await db_session.execute(select(Sesion))).scalars().all()
    assert len(sesiones) == 1
    s = sesiones[0]
    assert s.id_premisa == p.id
    assert s.id_juego == juegos[0].id
    assert s.descripcion == "Nivel 5, traer copia"
    assert s.plazas_totales == 4
    assert s.fecha == target

    # La tarjeta lleva el nombre de la premisa + la descripción de SESIÓN
    # (la específica gana sobre la de premisa)
    publicaciones = [
        _payload(c) for c in _send_message_calls(telegram_mock)
        if str(_payload(c).get("chat_id")) == E2E_CHAT_ID
    ]
    assert len(publicaciones) == 1
    text = publicaciones[0]["text"]
    assert "La maldición de Strahd" in text
    assert "Nivel 5, traer copia" in text   # descripción de la sesión
    assert "Ravenloft" not in text          # NO la de premisa (override)
    assert target.isoformat() in text


async def test_crear_sesion_reusa_juego_existente(
    http_client, telegram_mock, db_session, make_text_update, make_callback_update
):
    """Si el juego ya existe en el catálogo, no se duplica al añadirlo."""
    # Pre-existente en el catálogo global
    await http_client.post("/juegos", json={"nombre": "Vampiro"})

    tg_id = 20003
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="/start"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data="crear_sesion"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="bio"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="One-shot vampírico"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="/skip"),
    )
    # No tiene juegos en su lista → pulsa "añadir nuevo"
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data="juego_nuevo"),
    )
    # Escribe "vampiro" (ya existe, case-insensitive)
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="vampiro"),
    )
    # NO debe pedir confirmación: como ya existe, salta directo al calendario.
    target = _target_fecha()
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data=_cal_nav(target)),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data=_cal_pick(target)),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="3"),
    )
    # /skip de la nota específica de la sesión
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="/skip"),
    )

    juegos = (await db_session.execute(select(Juego))).scalars().all()
    assert [j.nombre for j in juegos] == ["Vampiro"]  # NO duplicado

    sesiones = (await db_session.execute(select(Sesion))).scalars().all()
    assert len(sesiones) == 1


async def test_crear_sesion_calendario_rechaza_fecha_pasada(
    http_client, telegram_mock, db_session, make_text_update, make_callback_update
):
    """El calendario no muestra días en el pasado, pero si llega un callback
    `cal_pick_<fecha-pasada>` (cliente alterado), el handler debe rechazarlo."""
    tg_id = 20002
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="/start"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data="crear_sesion"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="bio"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="Sesión X"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="/skip"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data="juego_nuevo"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="UnJuegoNuevo"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data="nuevo_juego_ok"),
    )
    # Inyecta callback de fecha pasada (algo que el calendario nunca expone).
    fecha_pasada = date.today() - timedelta(days=10)
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data=_cal_pick(fecha_pasada)),
    )

    # No se debe haber creado ninguna sesión: el flujo sigue en estado FECHA.
    sesiones = (await db_session.execute(select(Sesion))).scalars().all()
    assert sesiones == []


# ──────────────────────── Unirse a sesión ────────────────────────


async def test_unirse_full_flow_crea_pj_y_apunta(
    http_client, telegram_mock, db_session, make_text_update, make_callback_update
):
    # Setup: una persona DM crea una sesión (flujo completo nuevo)
    dm_tg = 30001
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="/start"))
    await http_client.post("/telegram/webhook", json=make_callback_update(telegram_id=dm_tg, data="crear_sesion"))
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="bio dm"))
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="Mi sesión"))
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="/skip"))
    await http_client.post("/telegram/webhook", json=make_callback_update(telegram_id=dm_tg, data="juego_nuevo"))
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="OneShot"))
    await http_client.post("/telegram/webhook", json=make_callback_update(telegram_id=dm_tg, data="nuevo_juego_ok"))
    target = _target_fecha()
    await http_client.post("/telegram/webhook", json=make_callback_update(telegram_id=dm_tg, data=_cal_nav(target)))
    await http_client.post("/telegram/webhook", json=make_callback_update(telegram_id=dm_tg, data=_cal_pick(target)))
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="3"))
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="/skip"))

    sesion = (await db_session.execute(select(Sesion))).scalar_one()

    # Otra persona se apunta
    pj_tg = 30002
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=pj_tg, text="/start", first_name="Aria"),
    )
    # Pulsa "apuntar_{id}" en la tarjeta de la sesión (callback desde el canal)
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(
            telegram_id=pj_tg, data=f"apuntar_{sesion.id}", from_channel=True
        ),
    )
    # Bot pide nombre del PJ vía DM
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=pj_tg, text="Aria la Hechicera"),
    )
    # Bot pide descripción → /skip
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=pj_tg, text="/skip"),
    )

    # ─── Comprobaciones ───
    persona_pj = (
        await db_session.execute(select(Persona).where(Persona.telegram_id == pj_tg))
    ).scalar_one()
    assert persona_pj.id_pj is not None
    pj = await db_session.get(PJ, persona_pj.id_pj)
    assert pj.nombre == "Aria la Hechicera"

    inscripcion = (
        await db_session.execute(
            select(SesionPJ).where(SesionPJ.id_sesion == sesion.id, SesionPJ.id_pj == pj.id)
        )
    ).scalar_one_or_none()
    assert inscripcion is not None
    assert inscripcion.acompanantes == 0
