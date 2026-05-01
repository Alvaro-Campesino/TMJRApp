"""Smoke test contra la app levantada con `docker compose up`.

Ejecuta:
    pip install -r requirements-dev.txt
    docker compose up -d
    pytest tests/test_api_smoke.py

No necesita TELEGRAM_TOKEN: la app entra en "modo API-only" si el token
no está configurado y el bot queda inhabilitado.
"""
from __future__ import annotations

import os
import time

import httpx
import pytest

BASE_URL = os.environ.get("TMJR_BASE_URL", "http://localhost:8000")
TG_ID = int(time.time() * 1000) % 2_000_000_000  # id único por ejecución


def test_health() -> None:
    r = httpx.get(f"{BASE_URL}/health", timeout=5.0)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_persona_dm_pj_sesion_apuntar() -> None:
    """Camino feliz: persona → DM → sesión → otra persona → PJ → apuntar."""
    # 1. Crear persona DM
    r = httpx.post(
        f"{BASE_URL}/personas",
        json={"telegram_id": TG_ID, "nombre": "Test DM"},
        timeout=5.0,
    )
    assert r.status_code == 200, r.text
    persona_dm = r.json()
    assert persona_dm["telegram_id"] == TG_ID

    # 2. Idempotencia: segunda llamada devuelve la misma fila
    r = httpx.post(
        f"{BASE_URL}/personas",
        json={"telegram_id": TG_ID, "nombre": "Test DM"},
        timeout=5.0,
    )
    assert r.json()["id"] == persona_dm["id"]

    # 3. Crear perfil DM
    r = httpx.post(
        f"{BASE_URL}/personas/{persona_dm['id']}/dm",
        json={"biografia": "DM de prueba"},
        timeout=5.0,
    )
    assert r.status_code == 200, r.text
    dm = r.json()

    # 4. Crear sesión con ese DM
    r = httpx.post(
        f"{BASE_URL}/sesiones",
        json={
            "id_dm": dm["id"],
            "fecha": "2030-01-04",
            "plazas_totales": 4,
            "plazas_sin_reserva": 1,
        },
        timeout=5.0,
    )
    assert r.status_code == 201, r.text
    sesion = r.json()

    # 5. Crear persona PJ y su perfil PJ
    r = httpx.post(
        f"{BASE_URL}/personas",
        json={"telegram_id": TG_ID + 1, "nombre": "Test PJ"},
        timeout=5.0,
    )
    persona_pj = r.json()

    r = httpx.post(
        f"{BASE_URL}/personas/{persona_pj['id']}/pj",
        json={"nombre": "Aria la Hechicera"},
        timeout=5.0,
    )
    assert r.status_code == 200, r.text
    pj = r.json()

    # 6. Apuntar el PJ a la sesión
    r = httpx.post(
        f"{BASE_URL}/sesiones/{sesion['id']}/apuntar",
        json={"id_pj": pj["id"], "acompanantes": 0},
        timeout=5.0,
    )
    assert r.status_code == 201, r.text

    # 7. Apuntar dos veces el mismo PJ → 409
    r = httpx.post(
        f"{BASE_URL}/sesiones/{sesion['id']}/apuntar",
        json={"id_pj": pj["id"], "acompanantes": 0},
        timeout=5.0,
    )
    assert r.status_code == 409


def test_persona_no_existente() -> None:
    r = httpx.get(f"{BASE_URL}/personas/by-telegram/0", timeout=5.0)
    assert r.status_code == 404
