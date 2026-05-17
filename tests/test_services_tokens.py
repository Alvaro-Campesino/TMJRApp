"""Tests del servicio de tokens de invitación."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from tmjr.db.models import TokenInvitacion
from tmjr.services import tokens as svc


async def test_crear_token_inserta_uno_activo(session):
    tok = await svc.crear_token(session, creador_telegram_id=42)
    assert tok.id is not None
    assert tok.token
    assert tok.revoked is False
    assert tok.created_by_telegram_id == 42

    activo = await svc.token_activo(session)
    assert activo is not None
    assert activo.id == tok.id


async def test_crear_token_revoca_anteriores(session):
    """Solo puede haber un token activo a la vez."""
    t1 = await svc.crear_token(session)
    t2 = await svc.crear_token(session)

    await session.refresh(t1)
    assert t1.revoked is True
    assert t2.revoked is False

    activo = await svc.token_activo(session)
    assert activo is not None
    assert activo.id == t2.id


async def test_validar_token_valido(session):
    tok = await svc.crear_token(session)
    found = await svc.validar(session, tok.token)
    assert found is not None
    assert found.id == tok.id


async def test_validar_token_revocado_devuelve_none(session):
    tok = await svc.crear_token(session)
    await svc.revocar_activos(session)
    found = await svc.validar(session, tok.token)
    assert found is None


async def test_validar_token_caducado_devuelve_none(session):
    """Forzamos expires_at en el pasado para verificar el caducado."""
    tok = await svc.crear_token(session, ttl_dias=1)
    tok.expires_at = datetime.utcnow() - timedelta(seconds=1)
    await session.commit()
    found = await svc.validar(session, tok.token)
    assert found is None


async def test_validar_token_inexistente_devuelve_none(session):
    assert await svc.validar(session, "no-existe") is None


async def test_token_activo_ignora_caducados(session):
    """Si el último creado está caducado, token_activo no lo devuelve."""
    tok = await svc.crear_token(session, ttl_dias=1)
    tok.expires_at = datetime.utcnow() - timedelta(seconds=1)
    await session.commit()
    assert await svc.token_activo(session) is None


async def test_ttl_dias_pueblan_expires_at(session):
    tok = await svc.crear_token(session, ttl_dias=7)
    assert tok.expires_at is not None
    delta = tok.expires_at - datetime.utcnow()
    assert timedelta(days=6, hours=23) < delta <= timedelta(days=7)


async def test_revocar_activos_no_toca_revocados(session):
    """Idempotencia: revocar dos veces no rompe el contador."""
    await svc.crear_token(session)
    n1 = await svc.revocar_activos(session)
    n2 = await svc.revocar_activos(session)
    rows = (await session.execute(select(TokenInvitacion))).scalars().all()
    assert all(t.revoked for t in rows)
    assert n1 == 1
    assert n2 == 0
