from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db import get_session
from tmjr.services import personas as svc

from .schemas import DMIn, DMOut, PersonaIn, PersonaOut, PJIn, PJOut

router = APIRouter(prefix="/personas", tags=["personas"])


@router.post("", response_model=PersonaOut, status_code=status.HTTP_200_OK)
async def upsert_persona(payload: PersonaIn, session: AsyncSession = Depends(get_session)):
    persona, _ = await svc.get_or_create_persona(
        session, telegram_id=payload.telegram_id, nombre=payload.nombre
    )
    return persona


@router.get("/by-telegram/{telegram_id}", response_model=PersonaOut)
async def get_by_telegram(telegram_id: int, session: AsyncSession = Depends(get_session)):
    persona = await svc.get_persona_by_telegram(session, telegram_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return persona


@router.post("/{persona_id}/dm", response_model=DMOut)
async def crear_perfil_dm(
    persona_id: int,
    payload: DMIn,
    session: AsyncSession = Depends(get_session),
):
    persona = await svc.get_persona(session, persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return await svc.ensure_dm(session, persona, biografia=payload.biografia)


@router.post("/{persona_id}/pj", response_model=PJOut)
async def crear_perfil_pj(
    persona_id: int,
    payload: PJIn,
    session: AsyncSession = Depends(get_session),
):
    persona = await svc.get_persona(session, persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    return await svc.ensure_pj(
        session, persona, nombre=payload.nombre, descripcion=payload.descripcion
    )
