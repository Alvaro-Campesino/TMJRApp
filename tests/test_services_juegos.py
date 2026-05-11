"""Unit tests del servicio de juegos: catálogo + listas por DM."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from tmjr.db.models import DMJuego, Juego
from tmjr.services import juegos as svc
from tmjr.services import personas as personas_svc


async def _dm(session, telegram_id: int) -> int:
    persona, _ = await personas_svc.get_or_create_persona(
        session, telegram_id=telegram_id, nombre="DM"
    )
    dm = await personas_svc.ensure_dm(session, persona)
    return dm.id


async def test_create_juego_y_list_all(session):
    a = await svc.create_juego(session, nombre="D&D 5e")
    b = await svc.create_juego(session, nombre="Vampiro")

    todos = await svc.list_all_juegos(session)
    nombres = [j.nombre for j in todos]
    assert nombres == sorted(nombres)
    assert {a.nombre, b.nombre}.issubset(set(nombres))


async def test_find_juego_por_nombre_es_case_insensitive(session):
    await svc.create_juego(session, nombre="Blades in the Dark")

    found = await svc.find_juego_by_name(session, "blades in the dark")
    assert found is not None
    assert found.nombre == "Blades in the Dark"

    found = await svc.find_juego_by_name(session, "  BLADES IN THE DARK  ")
    assert found is not None


async def test_get_or_create_juego_idempotente(session):
    j1, c1 = await svc.get_or_create_juego(session, nombre="Pathfinder 2e")
    j2, c2 = await svc.get_or_create_juego(session, nombre="pathfinder 2e")
    assert c1 is True
    assert c2 is False
    assert j1.id == j2.id

    rows = (await session.execute(select(Juego))).scalars().all()
    assert len([r for r in rows if r.nombre == "Pathfinder 2e"]) == 1


async def test_list_juegos_for_dm_filtra(session):
    id_dm = await _dm(session, 1)
    a = await svc.create_juego(session, nombre="Cthulhu")
    b = await svc.create_juego(session, nombre="Apocalypse World")
    # Solo enlazamos uno al DM
    await svc.add_juego_to_dm(session, id_dm=id_dm, id_juego=a.id)

    juegos_dm = await svc.list_juegos_for_dm(session, id_dm)
    assert [j.nombre for j in juegos_dm] == ["Cthulhu"]


async def test_add_juego_a_dm_es_idempotente(session):
    id_dm = await _dm(session, 2)
    j = await svc.create_juego(session, nombre="Mutant Year Zero")

    assert await svc.add_juego_to_dm(session, id_dm=id_dm, id_juego=j.id) is True
    assert await svc.add_juego_to_dm(session, id_dm=id_dm, id_juego=j.id) is False

    rows = (
        await session.execute(
            select(DMJuego).where(DMJuego.id_dm == id_dm, DMJuego.id_juego == j.id)
        )
    ).all()
    assert len(rows) == 1


async def test_add_juego_a_dm_inexistente(session):
    j = await svc.create_juego(session, nombre="Star Wars d6")
    with pytest.raises(ValueError, match="DM"):
        await svc.add_juego_to_dm(session, id_dm=9999, id_juego=j.id)


async def test_add_juego_inexistente_a_dm(session):
    id_dm = await _dm(session, 3)
    with pytest.raises(ValueError, match="Juego"):
        await svc.add_juego_to_dm(session, id_dm=id_dm, id_juego=9999)


async def test_list_juegos_not_in_dm_excluye_los_enlazados(session):
    id_dm = await _dm(session, 4)
    a = await svc.create_juego(session, nombre="Aria")
    b = await svc.create_juego(session, nombre="Brindis")
    c = await svc.create_juego(session, nombre="Cántico")
    # El DM ya tiene "Brindis" en su lista.
    await svc.add_juego_to_dm(session, id_dm=id_dm, id_juego=b.id)

    disponibles = await svc.list_juegos_not_in_dm(session, id_dm)
    nombres = [j.nombre for j in disponibles]
    assert nombres == ["Aria", "Cántico"]   # ordenado alfabéticamente y sin "Brindis"


async def test_list_juegos_not_in_dm_dm_sin_juegos_devuelve_todo(session):
    id_dm = await _dm(session, 5)
    await svc.create_juego(session, nombre="Solo")

    disponibles = await svc.list_juegos_not_in_dm(session, id_dm)
    assert [j.nombre for j in disponibles] == ["Solo"]
