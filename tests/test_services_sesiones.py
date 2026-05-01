"""Unit tests del servicio de sesiones: crear, apuntar, plazas, errores."""
from __future__ import annotations

from datetime import date

import pytest

from tmjr.services import personas as personas_svc
from tmjr.services import sesiones as svc


async def _persona_dm(session, telegram_id: int, nombre: str = "DM") -> int:
    persona, _ = await personas_svc.get_or_create_persona(
        session, telegram_id=telegram_id, nombre=nombre
    )
    dm = await personas_svc.ensure_dm(session, persona)
    return dm.id


async def _persona_pj(session, telegram_id: int, nombre: str = "PJ") -> int:
    persona, _ = await personas_svc.get_or_create_persona(
        session, telegram_id=telegram_id, nombre=nombre
    )
    pj = await personas_svc.ensure_pj(session, persona, nombre=nombre)
    return pj.id


async def test_crear_sesion_minima(session):
    id_dm = await _persona_dm(session, 1)
    s = await svc.crear_sesion(session, id_dm=id_dm, fecha=date(2030, 1, 4))
    assert s.id is not None
    assert s.id_dm == id_dm
    assert s.plazas_totales == 5
    assert s.plazas_sin_reserva == 1


async def test_crear_sesion_con_overrides(session):
    id_dm = await _persona_dm(session, 2)
    s = await svc.crear_sesion(
        session,
        id_dm=id_dm,
        fecha=date(2030, 1, 11),
        plazas_totales=3,
        plazas_sin_reserva=0,
    )
    assert s.plazas_totales == 3
    assert s.plazas_sin_reserva == 0


async def test_get_sesion_inexistente_devuelve_none(session):
    assert await svc.get_sesion(session, 9999) is None


async def test_apuntar_pj_camino_feliz(session):
    id_dm = await _persona_dm(session, 10)
    id_pj = await _persona_pj(session, 11, "PJ-1")
    s = await svc.crear_sesion(session, id_dm=id_dm, fecha=date(2030, 2, 1))

    sp = await svc.apuntar_pj(session, sesion_id=s.id, pj_id=id_pj)
    assert sp.id is not None
    assert sp.id_sesion == s.id
    assert sp.id_pj == id_pj
    assert sp.acompanantes == 0


async def test_apuntar_pj_dos_veces_falla(session):
    id_dm = await _persona_dm(session, 20)
    id_pj = await _persona_pj(session, 21, "PJ-2")
    s = await svc.crear_sesion(session, id_dm=id_dm, fecha=date(2030, 2, 8))

    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=id_pj)
    with pytest.raises(svc.YaApuntadoError):
        await svc.apuntar_pj(session, sesion_id=s.id, pj_id=id_pj)


async def test_apuntar_pj_a_sesion_inexistente(session):
    id_pj = await _persona_pj(session, 30, "PJ-3")
    with pytest.raises(ValueError, match="Sesion"):
        await svc.apuntar_pj(session, sesion_id=9999, pj_id=id_pj)


async def test_apuntar_pj_inexistente(session):
    id_dm = await _persona_dm(session, 40)
    s = await svc.crear_sesion(session, id_dm=id_dm, fecha=date(2030, 2, 15))
    with pytest.raises(ValueError, match="PJ"):
        await svc.apuntar_pj(session, sesion_id=s.id, pj_id=9999)


async def test_sesion_llena_sin_acompanantes(session):
    id_dm = await _persona_dm(session, 50)
    s = await svc.crear_sesion(
        session, id_dm=id_dm, fecha=date(2030, 3, 1), plazas_totales=2
    )
    pj1 = await _persona_pj(session, 51, "P1")
    pj2 = await _persona_pj(session, 52, "P2")
    pj3 = await _persona_pj(session, 53, "P3")

    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj1)
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj2)
    with pytest.raises(svc.SesionLlenaError):
        await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj3)


async def test_acompanantes_cuentan_para_plazas(session):
    id_dm = await _persona_dm(session, 60)
    s = await svc.crear_sesion(
        session, id_dm=id_dm, fecha=date(2030, 3, 8), plazas_totales=3
    )
    pj1 = await _persona_pj(session, 61, "Q1")
    pj2 = await _persona_pj(session, 62, "Q2")

    # 1 PJ con 1 acompañante = 2 plazas
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj1, acompanantes=1)
    # 1 PJ extra ya hace 3 → cabe
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj2, acompanantes=0)

    pj3 = await _persona_pj(session, 63, "Q3")
    with pytest.raises(svc.SesionLlenaError):
        await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj3)


async def test_plazas_ocupadas_calculo(session):
    id_dm = await _persona_dm(session, 70)
    s = await svc.crear_sesion(
        session, id_dm=id_dm, fecha=date(2030, 3, 15), plazas_totales=6
    )
    pj1 = await _persona_pj(session, 71, "R1")
    pj2 = await _persona_pj(session, 72, "R2")

    assert await svc.plazas_ocupadas(session, s.id) == 0
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj1, acompanantes=2)
    assert await svc.plazas_ocupadas(session, s.id) == 3  # 1 + 2
    await svc.apuntar_pj(session, sesion_id=s.id, pj_id=pj2, acompanantes=0)
    assert await svc.plazas_ocupadas(session, s.id) == 4
