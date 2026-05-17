"""Lógica de dominio sobre tokens de invitación.

Solo existe un token activo a la vez. `crear_token` revoca el anterior
automáticamente. Los registros previos (filas en `personas` con
`registrado_via_token_id`) se conservan: la revocación no toca al
historial, solo invalida nuevos registros.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db.models import TokenInvitacion


_TOKEN_BYTES = 24  # ~32 chars url-safe; cómodo para deep-links de Telegram.


def _new_token_string() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


async def crear_token(
    session: AsyncSession,
    *,
    creador_telegram_id: int | None = None,
    ttl_dias: int | None = None,
) -> TokenInvitacion:
    """Crea un token nuevo y revoca el anterior activo (si lo hay).

    `ttl_dias` opcional → `expires_at = now + ttl_dias`. Si es None, el
    token no caduca (solo se invalidará por revocación manual o por
    `crear_token` posterior).
    """
    await revocar_activos(session)

    expires_at = (
        datetime.utcnow() + timedelta(days=ttl_dias) if ttl_dias else None
    )
    tok = TokenInvitacion(
        token=_new_token_string(),
        created_by_telegram_id=creador_telegram_id,
        expires_at=expires_at,
    )
    session.add(tok)
    await session.commit()
    await session.refresh(tok)
    return tok


async def revocar_activos(session: AsyncSession) -> int:
    """Marca como revocados todos los tokens no revocados. Devuelve cuántos."""
    result = await session.execute(
        update(TokenInvitacion)
        .where(TokenInvitacion.revoked.is_(False))
        .values(revoked=True)
    )
    await session.commit()
    return result.rowcount or 0


async def token_activo(session: AsyncSession) -> TokenInvitacion | None:
    """Último token no revocado y no caducado, si existe."""
    now = datetime.utcnow()
    stmt = (
        select(TokenInvitacion)
        .where(TokenInvitacion.revoked.is_(False))
        .order_by(TokenInvitacion.created_at.desc())
    )
    for tok in (await session.execute(stmt)).scalars():
        if tok.expires_at is None or tok.expires_at > now:
            return tok
    return None


async def validar(
    session: AsyncSession, token_str: str
) -> TokenInvitacion | None:
    """Devuelve el token si existe, no está revocado y no ha caducado."""
    tok = (
        await session.execute(
            select(TokenInvitacion).where(TokenInvitacion.token == token_str)
        )
    ).scalar_one_or_none()
    if tok is None or tok.revoked:
        return None
    if tok.expires_at is not None and tok.expires_at <= datetime.utcnow():
        return None
    return tok
