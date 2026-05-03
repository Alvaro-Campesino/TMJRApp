from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db import get_session
from tmjr.services import juegos as svc

from .schemas import JuegoIn, JuegoOut

router = APIRouter(prefix="/juegos", tags=["juegos"])


@router.get("", response_model=list[JuegoOut])
async def listar_juegos(session: AsyncSession = Depends(get_session)):
    return await svc.list_all_juegos(session)


@router.post("", response_model=JuegoOut, status_code=status.HTTP_201_CREATED)
async def crear_juego(payload: JuegoIn, session: AsyncSession = Depends(get_session)):
    try:
        return await svc.create_juego(
            session, nombre=payload.nombre, descripcion=payload.descripcion
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe un juego con nombre '{payload.nombre}'"
        )
