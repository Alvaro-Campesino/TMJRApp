"""Unit tests del servicio de premisas."""
from __future__ import annotations

import pytest

from tmjr.services import juegos as juegos_svc
from tmjr.services import premisas as svc


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
