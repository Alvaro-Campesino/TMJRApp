"""Unit tests del servicio de premisas."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from tmjr.db.models import DMPremisa
from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as personas_svc
from tmjr.services import premisas as svc


async def _dm(session, telegram_id: int) -> int:
    persona, _ = await personas_svc.get_or_create_persona(
        session, telegram_id=telegram_id, nombre="DM"
    )
    dm = await personas_svc.ensure_dm(session, persona)
    return dm.id


async def test_crear_premisa_minima(session):
    p = await svc.crear_premisa(session, nombre="Una idea")
    assert p.id is not None
    assert p.nombre == "Una idea"
    assert p.id_juego is None
    assert p.descripcion is None


async def test_crear_premisa_completa(session):
    j = await juegos_svc.create_juego(session, nombre="Eldritch")
    p = await svc.crear_premisa(
        session,
        nombre="La maldición de Strahd",
        id_juego=j.id,
        descripcion="Aventura clásica de Ravenloft",
        aviso_contenido="Violencia gráfica, vampirismo",
    )
    assert p.id_juego == j.id
    assert p.descripcion == "Aventura clásica de Ravenloft"
    assert p.aviso_contenido == "Violencia gráfica, vampirismo"


async def test_crear_premisa_con_juego_inexistente(session):
    with pytest.raises(ValueError, match="Juego"):
        await svc.crear_premisa(session, nombre="X", id_juego=9999)


async def test_get_premisa_inexistente(session):
    assert await svc.get_premisa(session, 9999) is None


async def test_link_premisa_to_dm_es_idempotente(session):
    id_dm = await _dm(session, 100)
    p = await svc.crear_premisa(session, nombre="Heist en Doskvol")

    assert await svc.link_premisa_to_dm(
        session, id_dm=id_dm, id_premisa=p.id
    ) is True
    assert await svc.link_premisa_to_dm(
        session, id_dm=id_dm, id_premisa=p.id
    ) is False

    rows = (
        await session.execute(
            select(DMPremisa).where(
                DMPremisa.id_dm == id_dm, DMPremisa.id_premisa == p.id
            )
        )
    ).all()
    assert len(rows) == 1


async def test_link_premisa_to_dm_inexistente(session):
    p = await svc.crear_premisa(session, nombre="Solo")
    with pytest.raises(ValueError, match="DM"):
        await svc.link_premisa_to_dm(session, id_dm=9999, id_premisa=p.id)


async def test_link_premisa_inexistente_a_dm(session):
    id_dm = await _dm(session, 101)
    with pytest.raises(ValueError, match="Premisa"):
        await svc.link_premisa_to_dm(session, id_dm=id_dm, id_premisa=9999)


async def test_list_premisas_for_dm_y_not_in_dm(session):
    id_dm = await _dm(session, 102)
    a = await svc.crear_premisa(session, nombre="Alfa")
    b = await svc.crear_premisa(session, nombre="Beta")
    c = await svc.crear_premisa(session, nombre="Gamma")
    await svc.link_premisa_to_dm(session, id_dm=id_dm, id_premisa=b.id)

    enlazadas = await svc.list_premisas_for_dm(session, id_dm)
    assert [p.nombre for p in enlazadas] == ["Beta"]

    disponibles = await svc.list_premisas_not_in_dm(session, id_dm)
    assert [p.nombre for p in disponibles] == ["Alfa", "Gamma"]


async def test_list_premisas_for_dm_vacio(session):
    id_dm = await _dm(session, 103)
    assert await svc.list_premisas_for_dm(session, id_dm) == []


async def test_update_premisa_aplica_solo_no_none(session):
    p = await svc.crear_premisa(session, nombre="Original", descripcion="Desc")
    p2 = await svc.update_premisa(session, p, nombre="Renombrada")
    assert p2.nombre == "Renombrada"
    assert p2.descripcion == "Desc"  # no cambió

    # Cambiar a juego inexistente falla.
    with pytest.raises(ValueError, match="Juego"):
        await svc.update_premisa(session, p, id_juego=9999)


async def test_update_premisa_juego_existente(session):
    j = await juegos_svc.create_juego(session, nombre="UpdJuego")
    p = await svc.crear_premisa(session, nombre="ConJuego")
    p2 = await svc.update_premisa(session, p, id_juego=j.id)
    assert p2.id_juego == j.id


# ─────────────────────── tests de campañas ───────────────────────


async def test_campanias_flow(session):
    """Crear campaña + añadir/eliminar PJ fijo + materializar a sesión."""
    from datetime import datetime
    from tmjr.services import campanias as camp_svc
    from tmjr.services import sesiones as ses_svc

    id_dm = await _dm(session, 500)
    p = await svc.crear_premisa(session, nombre="Strahd")
    j = await juegos_svc.create_juego(session, nombre="JuegoCmp")

    # Crear campaña.
    c = await camp_svc.crear_campania(session, id_dm=id_dm, id_premisa=p.id)
    assert c.id is not None
    assert c.id_dm == id_dm

    # Sin sesiones todavía: next_numero == 1.
    assert await camp_svc.next_numero(session, c.id) == 1

    # Crear PJs y añadir como fijos (idempotencia).
    persona1, _ = await personas_svc.get_or_create_persona(
        session, telegram_id=501, nombre="Jugador1"
    )
    pj1 = await personas_svc.ensure_pj(session, persona1)
    persona2, _ = await personas_svc.get_or_create_persona(
        session, telegram_id=502, nombre="Jugador2"
    )
    pj2 = await personas_svc.ensure_pj(session, persona2)

    assert await camp_svc.add_pj_fijo(
        session, id_campania=c.id, id_pj=pj1.id
    ) is True
    assert await camp_svc.add_pj_fijo(
        session, id_campania=c.id, id_pj=pj1.id
    ) is False  # idempotente
    assert await camp_svc.add_pj_fijo(
        session, id_campania=c.id, id_pj=pj2.id
    ) is True

    # `list_pjs_fijos` devuelve [(PJ, persona_nombre)]; el nombre del PJ
    # es siempre el de la persona (Jugador1/Jugador2 aquí).
    fijos = await camp_svc.list_pjs_fijos(session, c.id)
    assert {nombre for _, nombre in fijos} == {"Jugador1", "Jugador2"}

    # Crear una sesión nº2 de la campaña y materializar PJs.
    s2 = await ses_svc.crear_sesion(
        session, id_dm=id_dm, id_juego=j.id,
        fecha=datetime(2030, 9, 1, 18, 0),
        id_premisa=p.id, id_campania=c.id, numero=2,
    )
    assert await camp_svc.next_numero(session, c.id) == 3

    nuevos = await camp_svc.materializar_pjs_a_sesion(session, s2)
    assert nuevos == 2

    # list_telegram_de_pjs_fijos devuelve el nombre de la Persona (no
    # hay PJ.nombre; el nombre del PJ ES el de la persona).
    avisos = await camp_svc.list_telegram_de_pjs_fijos(session, c.id)
    assert sorted(avisos) == sorted([(501, "Jugador1"), (502, "Jugador2")])

    # Eliminar pj1: debería borrarlo de fijos y de la sesión futura s2.
    assert await camp_svc.remove_pj_fijo(
        session, id_campania=c.id, id_pj=pj1.id
    ) is True
    fijos2 = await camp_svc.list_pjs_fijos(session, c.id)
    assert {nombre for _, nombre in fijos2} == {"Jugador2"}

    # pj1 ya no debe estar en sesion_pj de s2 (futura).
    from sqlalchemy import select
    from tmjr.db.models import SesionPJ
    rows = (
        await session.execute(
            select(SesionPJ).where(
                SesionPJ.id_sesion == s2.id, SesionPJ.id_pj == pj1.id
            )
        )
    ).all()
    assert rows == []
