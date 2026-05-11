"""Tests de endpoints de /personas usando ASGITransport (sin lifespan)."""
from __future__ import annotations

import pytest


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_post_personas_crea(client):
    r = await client.post("/personas", json={"telegram_id": 100, "nombre": "Quien"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["telegram_id"] == 100
    assert data["nombre"] == "Quien"
    assert data["id_pj"] is None
    assert data["id_master"] is None


async def test_post_personas_es_idempotente(client):
    r1 = await client.post("/personas", json={"telegram_id": 200, "nombre": "Quien"})
    r2 = await client.post("/personas", json={"telegram_id": 200, "nombre": "OTRO"})
    assert r1.json()["id"] == r2.json()["id"]


async def test_get_persona_by_telegram(client):
    await client.post("/personas", json={"telegram_id": 300, "nombre": "X"})
    r = await client.get("/personas/by-telegram/300")
    assert r.status_code == 200
    assert r.json()["telegram_id"] == 300


async def test_get_persona_by_telegram_404(client):
    r = await client.get("/personas/by-telegram/999999")
    assert r.status_code == 404


async def test_post_dm_crea_perfil(client):
    persona = (await client.post(
        "/personas", json={"telegram_id": 400, "nombre": "DM"}
    )).json()
    r = await client.post(
        f"/personas/{persona['id']}/dm", json={"biografia": "veterana"}
    )
    assert r.status_code == 200, r.text
    dm = r.json()
    assert dm["biografia"] == "veterana"


async def test_post_dm_idempotente(client):
    persona = (await client.post(
        "/personas", json={"telegram_id": 500, "nombre": "DM2"}
    )).json()
    dm1 = (await client.post(f"/personas/{persona['id']}/dm", json={})).json()
    dm2 = (await client.post(f"/personas/{persona['id']}/dm", json={})).json()
    assert dm1["id"] == dm2["id"]


async def test_post_dm_persona_inexistente(client):
    r = await client.post("/personas/99999/dm", json={})
    assert r.status_code == 404


async def test_post_pj_crea_perfil(client):
    persona = (await client.post(
        "/personas", json={"telegram_id": 600, "nombre": "PJ"}
    )).json()
    r = await client.post(
        f"/personas/{persona['id']}/pj",
        json={"nombre": "Aria", "descripcion": "hechicera"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Aria"


async def test_post_pj_idempotente(client):
    persona = (await client.post(
        "/personas", json={"telegram_id": 700, "nombre": "PJ2"}
    )).json()
    pj1 = (await client.post(
        f"/personas/{persona['id']}/pj", json={"nombre": "Primero"}
    )).json()
    pj2 = (await client.post(
        f"/personas/{persona['id']}/pj", json={"nombre": "Segundo"}
    )).json()
    assert pj1["id"] == pj2["id"]
    assert pj2["nombre"] == "Primero"  # mantiene el original


async def test_post_pj_persona_inexistente(client):
    r = await client.post("/personas/99999/pj", json={"nombre": "Nadie"})
    assert r.status_code == 404


async def test_post_personas_validacion_pydantic(client):
    # nombre vacío rechazado
    r = await client.post("/personas", json={"telegram_id": 1, "nombre": ""})
    assert r.status_code == 422
