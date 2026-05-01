"""End-to-end de los flujos del bot:

- /start crea persona en BD y manda saludo.
- Crear sesión: persona sin DM → bot pide bio → fecha → plazas → crea sesión y publica tarjeta.
- Unirse a sesión: persona sin PJ pulsa botón → bot pide nombre/desc del PJ → apunta.

La API HTTP de Telegram está mockeada con respx; la BD es Postgres ephemero.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from tests.e2e.conftest import E2E_CHAT_ID, E2E_TOKEN
from tmjr.db.models import DM, PJ, Persona, Sesion, SesionPJ


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


async def test_crear_sesion_full_flow_crea_dm_y_publica(
    http_client, telegram_mock, db_session, make_text_update, make_callback_update
):
    tg_id = 20001

    # 1. /start → persona existe
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="/start", first_name="DM-Test"),
    )

    # 2. Pulsa "Crear sesión" en el menú
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data="crear_sesion"),
    )

    # 3. La persona aún no es DM → bot pide biografía. Responde con texto.
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="DM con 5 años de experiencia"),
    )

    # 4. Responde fecha
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="2030-09-07"),
    )

    # 5. Responde plazas
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="4"),
    )

    # ─── Comprobaciones ───
    persona = (
        await db_session.execute(select(Persona).where(Persona.telegram_id == tg_id))
    ).scalar_one()
    assert persona.id_master is not None, "La persona debería tener perfil DM"

    dm = await db_session.get(DM, persona.id_master)
    assert dm.biografia == "DM con 5 años de experiencia"

    sesiones = (await db_session.execute(select(Sesion))).scalars().all()
    assert len(sesiones) == 1
    s = sesiones[0]
    assert s.id_dm == dm.id
    assert s.plazas_totales == 4
    assert str(s.fecha) == "2030-09-07"

    # La tarjeta se publicó en el canal: hay un sendMessage cuyo chat_id == E2E_CHAT_ID
    publicaciones = [
        _payload(c) for c in _send_message_calls(telegram_mock)
        if str(_payload(c).get("chat_id")) == E2E_CHAT_ID
    ]
    assert len(publicaciones) == 1
    assert "Sesión" in publicaciones[0]["text"]
    assert "2030-09-07" in publicaciones[0]["text"]


async def test_crear_sesion_fecha_invalida_repregunta(
    http_client, telegram_mock, db_session, make_text_update, make_callback_update
):
    tg_id = 20002
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="/start"),
    )
    await http_client.post(
        "/telegram/webhook",
        json=make_callback_update(telegram_id=tg_id, data="crear_sesion"),
    )
    # Bio
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="bio"),
    )
    # Fecha mal formateada
    await http_client.post(
        "/telegram/webhook",
        json=make_text_update(telegram_id=tg_id, text="ayer"),
    )

    # No se creó sesión todavía
    sesiones = (await db_session.execute(select(Sesion))).scalars().all()
    assert sesiones == []

    # El bot replicó con el mensaje de error
    last = _payload(_send_message_calls(telegram_mock)[-1])
    assert "no válid" in last["text"].lower() or "AAAA" in last["text"]


# ──────────────────────── Unirse a sesión ────────────────────────


async def test_unirse_full_flow_crea_pj_y_apunta(
    http_client, telegram_mock, db_session, make_text_update, make_callback_update
):
    # Setup: una persona DM crea una sesión
    dm_tg = 30001
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="/start"))
    await http_client.post("/telegram/webhook", json=make_callback_update(telegram_id=dm_tg, data="crear_sesion"))
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="bio dm"))
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="2030-10-05"))
    await http_client.post("/telegram/webhook", json=make_text_update(telegram_id=dm_tg, text="3"))

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
