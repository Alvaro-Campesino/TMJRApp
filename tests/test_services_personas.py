"""Unit tests del servicio de personas: idempotencia y enlazados 1:1."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from tmjr.db.models import DM, PJ, Persona
from tmjr.services import personas as svc


async def test_get_or_create_persona_crea_si_no_existe(session):
    persona, created = await svc.get_or_create_persona(
        session, telegram_id=42, nombre="Alvaro"
    )
    assert created is True
    assert persona.id is not None
    assert persona.telegram_id == 42
    assert persona.nombre == "Alvaro"


async def test_get_or_create_persona_es_idempotente(session):
    p1, c1 = await svc.get_or_create_persona(session, telegram_id=99, nombre="A")
    p2, c2 = await svc.get_or_create_persona(session, telegram_id=99, nombre="OTRO")
    assert c1 is True
    assert c2 is False
    assert p1.id == p2.id
    # No machaca el nombre original
    assert p2.nombre == "A"


async def test_get_persona_by_telegram_inexistente_devuelve_none(session):
    assert await svc.get_persona_by_telegram(session, 12345) is None


async def test_ensure_dm_crea_y_enlaza(session):
    persona, _ = await svc.get_or_create_persona(session, telegram_id=1, nombre="DM")
    dm = await svc.ensure_dm(session, persona, biografia="bio test")

    assert dm.id is not None
    assert dm.biografia == "bio test"
    # La persona quedó enlazada
    persona_db = (
        await session.execute(select(Persona).where(Persona.id == persona.id))
    ).scalar_one()
    assert persona_db.id_master == dm.id


async def test_ensure_dm_es_idempotente(session):
    persona, _ = await svc.get_or_create_persona(session, telegram_id=2, nombre="DM2")
    dm1 = await svc.ensure_dm(session, persona, biografia="primera")
    dm2 = await svc.ensure_dm(session, persona, biografia="segunda")
    assert dm1.id == dm2.id

    # Y solo hay una fila en dm
    rows = (await session.execute(select(DM))).scalars().all()
    assert len(rows) == 1


async def test_ensure_pj_crea_y_enlaza(session):
    persona, _ = await svc.get_or_create_persona(session, telegram_id=3, nombre="PJ")
    pj = await svc.ensure_pj(session, persona, nombre="Aria", descripcion="hechicera")

    assert pj.id is not None
    assert pj.nombre == "Aria"
    persona_db = (
        await session.execute(select(Persona).where(Persona.id == persona.id))
    ).scalar_one()
    assert persona_db.id_pj == pj.id


async def test_ensure_pj_es_idempotente(session):
    persona, _ = await svc.get_or_create_persona(session, telegram_id=4, nombre="PJ4")
    pj1 = await svc.ensure_pj(session, persona, nombre="X")
    pj2 = await svc.ensure_pj(session, persona, nombre="OTRO")
    assert pj1.id == pj2.id

    rows = (await session.execute(select(PJ))).scalars().all()
    assert len(rows) == 1
    # Mantiene el nombre original
    assert pj2.nombre == "X"


async def test_persona_puede_ser_dm_y_pj_a_la_vez(session):
    persona, _ = await svc.get_or_create_persona(session, telegram_id=5, nombre="Dual")
    dm = await svc.ensure_dm(session, persona)
    pj = await svc.ensure_pj(session, persona, nombre="Dual-PJ")

    persona_db = await svc.get_persona(session, persona.id)
    assert persona_db.id_master == dm.id
    assert persona_db.id_pj == pj.id
