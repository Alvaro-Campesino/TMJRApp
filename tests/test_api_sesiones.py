"""Tests de endpoints de /sesiones usando ASGITransport (sin lifespan)."""
from __future__ import annotations

import pytest


async def _crear_dm(client, telegram_id: int) -> int:
    persona = (await client.post(
        "/personas", json={"telegram_id": telegram_id, "nombre": f"DM{telegram_id}"}
    )).json()
    dm = (await client.post(f"/personas/{persona['id']}/dm", json={})).json()
    return dm["id"]


async def _crear_pj(client, telegram_id: int) -> int:
    persona = (await client.post(
        "/personas", json={"telegram_id": telegram_id, "nombre": f"PJ{telegram_id}"}
    )).json()
    pj = (await client.post(
        f"/personas/{persona['id']}/pj", json={"nombre": f"Personaje{telegram_id}"}
    )).json()
    return pj["id"]


async def _crear_juego(client, nombre: str) -> int:
    return (await client.post("/juegos", json={"nombre": nombre})).json()["id"]


async def test_post_sesiones_201(client):
    id_dm = await _crear_dm(client, 1000)
    id_juego = await _crear_juego(client, "JuegoApi1")
    r = await client.post(
        "/sesiones",
        json={"id_dm": id_dm, "id_juego": id_juego,
              "fecha": "2030-04-04", "plazas_totales": 4},
    )
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["id_dm"] == id_dm
    assert s["id_juego"] == id_juego
    assert s["plazas_totales"] == 4
    assert s["descripcion"] is None


async def test_post_sesiones_con_descripcion(client):
    id_dm = await _crear_dm(client, 1050)
    id_juego = await _crear_juego(client, "JuegoApi1b")
    r = await client.post(
        "/sesiones",
        json={
            "id_dm": id_dm, "id_juego": id_juego, "fecha": "2030-04-05",
            "descripcion": "Lleva los dados",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["descripcion"] == "Lleva los dados"


async def test_post_sesiones_sin_id_juego_422(client):
    """id_juego es required en el schema."""
    id_dm = await _crear_dm(client, 1075)
    r = await client.post(
        "/sesiones", json={"id_dm": id_dm, "fecha": "2030-04-04"}
    )
    assert r.status_code == 422


async def test_post_sesiones_descripcion_demasiado_larga_422(client):
    id_dm = await _crear_dm(client, 1080)
    id_juego = await _crear_juego(client, "JuegoApi1c")
    r = await client.post(
        "/sesiones",
        json={
            "id_dm": id_dm, "id_juego": id_juego, "fecha": "2030-04-06",
            "descripcion": "x" * 401,
        },
    )
    assert r.status_code == 422


async def test_post_sesiones_validacion_plazas(client):
    id_dm = await _crear_dm(client, 1100)
    id_juego = await _crear_juego(client, "JuegoApi2")
    r = await client.post(
        "/sesiones",
        json={"id_dm": id_dm, "id_juego": id_juego,
              "fecha": "2030-04-04", "plazas_totales": 0},
    )
    assert r.status_code == 422
    r = await client.post(
        "/sesiones",
        json={"id_dm": id_dm, "id_juego": id_juego,
              "fecha": "2030-04-04", "plazas_totales": 7},
    )
    assert r.status_code == 422


async def test_get_sesion_404(client):
    r = await client.get("/sesiones/9999")
    assert r.status_code == 404


async def test_get_sesion_ok(client):
    id_dm = await _crear_dm(client, 1200)
    id_juego = await _crear_juego(client, "JuegoApi3")
    s = (await client.post(
        "/sesiones",
        json={"id_dm": id_dm, "id_juego": id_juego, "fecha": "2030-05-04"},
    )).json()
    r = await client.get(f"/sesiones/{s['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == s["id"]


async def test_apuntar_pj_201(client):
    id_dm = await _crear_dm(client, 1300)
    id_pj = await _crear_pj(client, 1301)
    id_juego = await _crear_juego(client, "JuegoApi4")
    s = (await client.post(
        "/sesiones",
        json={"id_dm": id_dm, "id_juego": id_juego, "fecha": "2030-05-11"},
    )).json()
    r = await client.post(
        f"/sesiones/{s['id']}/apuntar", json={"id_pj": id_pj, "acompanantes": 0}
    )
    assert r.status_code == 201, r.text


async def test_apuntar_pj_dos_veces_409(client):
    id_dm = await _crear_dm(client, 1400)
    id_pj = await _crear_pj(client, 1401)
    id_juego = await _crear_juego(client, "JuegoApi5")
    s = (await client.post(
        "/sesiones",
        json={"id_dm": id_dm, "id_juego": id_juego, "fecha": "2030-05-18"},
    )).json()
    await client.post(f"/sesiones/{s['id']}/apuntar", json={"id_pj": id_pj})
    r = await client.post(f"/sesiones/{s['id']}/apuntar", json={"id_pj": id_pj})
    assert r.status_code == 409
    assert "ya está apuntado" in r.json()["detail"].lower()


async def test_apuntar_sesion_llena_409(client):
    id_dm = await _crear_dm(client, 1500)
    id_juego = await _crear_juego(client, "JuegoApi6")
    s = (await client.post(
        "/sesiones",
        json={"id_dm": id_dm, "id_juego": id_juego,
              "fecha": "2030-06-01", "plazas_totales": 1},
    )).json()
    pj1 = await _crear_pj(client, 1501)
    pj2 = await _crear_pj(client, 1502)

    await client.post(f"/sesiones/{s['id']}/apuntar", json={"id_pj": pj1})
    r = await client.post(f"/sesiones/{s['id']}/apuntar", json={"id_pj": pj2})
    assert r.status_code == 409
    assert "plazas" in r.json()["detail"].lower()


async def test_apuntar_pj_inexistente_404(client):
    id_dm = await _crear_dm(client, 1600)
    id_juego = await _crear_juego(client, "JuegoApi7")
    s = (await client.post(
        "/sesiones",
        json={"id_dm": id_dm, "id_juego": id_juego, "fecha": "2030-06-08"},
    )).json()
    r = await client.post(
        f"/sesiones/{s['id']}/apuntar", json={"id_pj": 99999}
    )
    assert r.status_code == 404
