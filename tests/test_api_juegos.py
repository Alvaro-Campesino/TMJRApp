"""Tests del router /juegos y /personas/{id}/dm/juegos."""
from __future__ import annotations

import pytest


async def _crear_persona_dm(client, telegram_id: int) -> int:
    persona = (await client.post(
        "/personas", json={"telegram_id": telegram_id, "nombre": f"DM{telegram_id}"}
    )).json()
    await client.post(f"/personas/{persona['id']}/dm", json={})
    return persona["id"]


async def test_listar_juegos_vacio(client):
    r = await client.get("/juegos")
    assert r.status_code == 200
    assert r.json() == []


async def test_crear_y_listar_juego(client):
    r = await client.post("/juegos", json={"nombre": "D&D 5e"})
    assert r.status_code == 201, r.text
    juego = r.json()
    assert juego["nombre"] == "D&D 5e"

    r = await client.get("/juegos")
    assert any(j["nombre"] == "D&D 5e" for j in r.json())


async def test_crear_juego_duplicado_409(client):
    await client.post("/juegos", json={"nombre": "Vampiro"})
    r = await client.post("/juegos", json={"nombre": "Vampiro"})
    assert r.status_code == 409


async def test_listar_juegos_de_dm_vacio(client):
    persona_id = await _crear_persona_dm(client, 5001)
    r = await client.get(f"/personas/{persona_id}/dm/juegos")
    assert r.status_code == 200
    assert r.json() == []


async def test_añadir_juego_existente_a_dm(client):
    persona_id = await _crear_persona_dm(client, 5002)
    juego = (await client.post("/juegos", json={"nombre": "Pathfinder"})).json()

    r = await client.post(
        f"/personas/{persona_id}/dm/juegos", json={"id_juego": juego["id"]}
    )
    assert r.status_code == 200
    assert r.json()["nombre"] == "Pathfinder"

    juegos = (await client.get(f"/personas/{persona_id}/dm/juegos")).json()
    assert [j["nombre"] for j in juegos] == ["Pathfinder"]


async def test_añadir_juego_por_nombre_lo_crea_si_no_existe(client):
    persona_id = await _crear_persona_dm(client, 5003)
    r = await client.post(
        f"/personas/{persona_id}/dm/juegos", json={"nombre": "Cthulhu Confidential"}
    )
    assert r.status_code == 200
    assert r.json()["nombre"] == "Cthulhu Confidential"

    todos = (await client.get("/juegos")).json()
    assert any(j["nombre"] == "Cthulhu Confidential" for j in todos)


async def test_añadir_juego_por_nombre_reusa_si_existe(client):
    persona_id = await _crear_persona_dm(client, 5004)
    await client.post("/juegos", json={"nombre": "Apocalypse World"})

    r = await client.post(
        f"/personas/{persona_id}/dm/juegos", json={"nombre": "apocalypse world"}
    )
    assert r.status_code == 200

    todos = (await client.get("/juegos")).json()
    nombres = [j["nombre"] for j in todos]
    # Sigue habiendo solo uno (el original con su capitalización)
    assert nombres.count("Apocalypse World") == 1


async def test_añadir_juego_sin_id_ni_nombre_422(client):
    persona_id = await _crear_persona_dm(client, 5005)
    r = await client.post(f"/personas/{persona_id}/dm/juegos", json={})
    assert r.status_code == 422


async def test_listar_juegos_dm_inexistente_404(client):
    r = await client.get("/personas/99999/dm/juegos")
    assert r.status_code == 404


async def test_persona_sin_dm_no_puede_listar_juegos(client):
    persona = (await client.post(
        "/personas", json={"telegram_id": 5006, "nombre": "Solo persona"}
    )).json()
    r = await client.get(f"/personas/{persona['id']}/dm/juegos")
    assert r.status_code == 404
