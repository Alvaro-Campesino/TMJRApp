"""Tests del servicio de suscripciones a premisas."""
from __future__ import annotations

from datetime import datetime

from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as premisas_svc
from tmjr.services import sesiones as sesiones_svc
from tmjr.services import suscripciones as svc
from tmjr.services import campanias as campanias_svc


async def _persona(session, telegram_id: int, nombre: str = "P"):
    p, _ = await personas_svc.get_or_create_persona(
        session, telegram_id=telegram_id, nombre=nombre
    )
    return p


async def _persona_dm(session, telegram_id: int, nombre: str = "DM"):
    p = await _persona(session, telegram_id, nombre)
    dm = await personas_svc.ensure_dm(session, p)
    return p, dm


async def _premisa(session, dm_id: int, nombre: str = "Prem", *, link=True):
    j, _ = await juegos_svc.get_or_create_juego(
        session, nombre=f"J-{nombre}"
    )
    p = await premisas_svc.crear_premisa(
        session, nombre=nombre, descripcion="d", id_juego=j.id
    )
    if link:
        await premisas_svc.link_premisa_to_dm(
            session, id_dm=dm_id, id_premisa=p.id
        )
    return p


async def test_subscribe_idempotente(session):
    persona = await _persona(session, 1, "A")
    _, dm = await _persona_dm(session, 99, "DM")
    prem = await _premisa(session, dm.id)

    sub1, created1 = await svc.subscribe(
        session, persona_id=persona.id, premisa_id=prem.id
    )
    sub2, created2 = await svc.subscribe(
        session, persona_id=persona.id, premisa_id=prem.id
    )
    assert created1 is True
    assert created2 is False
    assert sub1.id == sub2.id


async def test_unsubscribe(session):
    persona = await _persona(session, 2, "B")
    _, dm = await _persona_dm(session, 98, "DM")
    prem = await _premisa(session, dm.id, "Prem2")

    await svc.subscribe(
        session, persona_id=persona.id, premisa_id=prem.id
    )
    assert await svc.unsubscribe(
        session, persona_id=persona.id, premisa_id=prem.id
    ) is True
    assert await svc.unsubscribe(
        session, persona_id=persona.id, premisa_id=prem.id
    ) is False


async def test_list_by_persona(session):
    persona = await _persona(session, 3, "C")
    _, dm = await _persona_dm(session, 97, "DM")
    p1 = await _premisa(session, dm.id, "A-prem")
    p2 = await _premisa(session, dm.id, "B-prem")
    await _premisa(session, dm.id, "C-prem")  # sin suscribir

    await svc.subscribe(session, persona_id=persona.id, premisa_id=p2.id)
    await svc.subscribe(session, persona_id=persona.id, premisa_id=p1.id)

    suscritas = await svc.list_by_persona(session, persona.id)
    assert [p.nombre for p in suscritas] == ["A-prem", "B-prem"]


async def test_dms_que_han_usado_premisa_via_catalogo(session):
    _, dm = await _persona_dm(session, 96, "DM_cat")
    prem = await _premisa(session, dm.id, "EnCatalogo")
    ids = await svc.dms_que_han_usado_premisa(session, prem.id)
    assert dm.id in ids


async def test_dms_que_han_usado_premisa_via_sesion(session):
    # DM_A crea la premisa (queda enlazada a su catálogo).
    _, dm_a = await _persona_dm(session, 95, "DM_A")
    prem = await _premisa(session, dm_a.id, "Compartida")

    # DM_B publica una sesión con esa premisa, SIN tenerla en su catálogo.
    _, dm_b = await _persona_dm(session, 94, "DM_B")
    j, _ = await juegos_svc.get_or_create_juego(session, nombre="J-via-ses")
    await sesiones_svc.crear_sesion(
        session, id_dm=dm_b.id, id_juego=j.id,
        fecha=datetime(2030, 6, 1, 18, 0), id_premisa=prem.id,
    )

    ids = await svc.dms_que_han_usado_premisa(session, prem.id)
    assert dm_a.id in ids  # catálogo
    assert dm_b.id in ids  # sesión publicada


async def test_premisas_usadas_por_dm_con_suscriptores(session):
    persona = await _persona(session, 4, "Sub")
    _, dm = await _persona_dm(session, 93, "DM_X")
    p_con = await _premisa(session, dm.id, "ConSubs")
    p_sin = await _premisa(session, dm.id, "SinSubs")

    await svc.subscribe(session, persona_id=persona.id, premisa_id=p_con.id)

    resultado = await svc.premisas_usadas_por_dm_con_suscriptores(
        session, dm.id
    )
    nombres = [(p.nombre, c) for p, c in resultado]
    assert ("ConSubs", 1) in nombres
    assert ("SinSubs", 0) not in [(n, c) for n, c in nombres]  # filtrada
    assert all(n != "SinSubs" for n, _ in nombres)


async def test_should_notify_subscribers_one_shot(session):
    _, dm = await _persona_dm(session, 92, "DM_OS")
    prem = await _premisa(session, dm.id, "OS")
    j, _ = await juegos_svc.get_or_create_juego(session, nombre="J-OS")

    sesion = await sesiones_svc.crear_sesion(
        session, id_dm=dm.id, id_juego=j.id,
        fecha=datetime(2030, 6, 5, 18, 0), id_premisa=prem.id,
    )
    assert await svc.should_notify_subscribers(session, sesion) is True


async def test_should_notify_subscribers_primera_de_campania(session):
    _, dm = await _persona_dm(session, 91, "DM_C")
    prem = await _premisa(session, dm.id, "Camp")
    j, _ = await juegos_svc.get_or_create_juego(session, nombre="J-Camp")

    camp = await campanias_svc.crear_campania(
        session, id_premisa=prem.id, id_dm=dm.id
    )
    s1 = await sesiones_svc.crear_sesion(
        session, id_dm=dm.id, id_juego=j.id,
        fecha=datetime(2030, 7, 1, 18, 0),
        id_premisa=prem.id, id_campania=camp.id,
    )
    s2 = await sesiones_svc.crear_sesion(
        session, id_dm=dm.id, id_juego=j.id,
        fecha=datetime(2030, 7, 8, 18, 0),
        id_premisa=prem.id, id_campania=camp.id,
    )
    assert await svc.should_notify_subscribers(session, s1) is True
    assert await svc.should_notify_subscribers(session, s2) is False


async def test_should_notify_subscribers_sin_premisa(session):
    _, dm = await _persona_dm(session, 90, "DM_N")
    j, _ = await juegos_svc.get_or_create_juego(session, nombre="J-N")
    sesion = await sesiones_svc.crear_sesion(
        session, id_dm=dm.id, id_juego=j.id,
        fecha=datetime(2030, 7, 15, 18, 0),
    )
    assert await svc.should_notify_subscribers(session, sesion) is False
