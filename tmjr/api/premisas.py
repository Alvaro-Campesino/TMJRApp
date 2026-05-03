from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db import get_session
from tmjr.services import premisas as svc

from .schemas import  PremisaIn, PremisaOut

router = APIRouter(prefix="/premisas", tags=["premisas"])


@router.post("", response_model=PremisaOut, status_code=status.HTTP_201_CREATED)
async def crear_premisa(payload: , session: AsyncSession = Depends(get_session)):
    return await svc.crear_premisa(
        session,
        nombre = payload.nombre,
        id_juego=payload.id_juego,
        descripcion=payload.descripcion,
        aviso_contenido=payload.aviso_contenido,
    )


@router.get("/{premisa_id}", response_model=PremisaOut)
async def get_premisa(premisa_id: int, session: AsyncSession = Depends(get_session)):
    premisa = await svc.get_premisa(session, premisa_id)
    if premisa is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return premisa

## TODO hacer el update