from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db import get_session
from tmjr.services import sesiones as svc

from .schemas import ApuntarseIn, SesionIn, SesionOut, SesionPJOut

router = APIRouter(prefix="/sesiones", tags=["sesiones"])


@router.post("", response_model=SesionOut, status_code=status.HTTP_201_CREATED)
async def crear_sesion(payload: SesionIn, session: AsyncSession = Depends(get_session)):
    return await svc.crear_sesion(
        session,
        id_dm=payload.id_dm,
        fecha=payload.fecha,
        plazas_totales=payload.plazas_totales,
        plazas_sin_reserva=payload.plazas_sin_reserva,
        id_premisa=payload.id_premisa,
        id_campania=payload.id_campania,
        numero=payload.numero,
    )


@router.get("/{sesion_id}", response_model=SesionOut)
async def get_sesion(sesion_id: int, session: AsyncSession = Depends(get_session)):
    sesion = await svc.get_sesion(session, sesion_id)
    if sesion is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return sesion


@router.post("/{sesion_id}/apuntar", response_model=SesionPJOut, status_code=status.HTTP_201_CREATED)
async def apuntar(
    sesion_id: int,
    payload: ApuntarseIn,
    session: AsyncSession = Depends(get_session),
):
    try:
        return await svc.apuntar_pj(
            session,
            sesion_id=sesion_id,
            pj_id=payload.id_pj,
            acompanantes=payload.acompanantes,
        )
    except svc.YaApuntadoError:
        raise HTTPException(status_code=409, detail="El PJ ya está apuntado")
    except svc.SesionLlenaError:
        raise HTTPException(status_code=409, detail="No quedan plazas")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
