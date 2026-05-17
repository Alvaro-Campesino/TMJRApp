from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tmjr.db import get_session
from tmjr.services import juegos as juegos_svc
from tmjr.services import personas as svc

from .schemas import DMIn, DMJuegoIn, DMOut, JuegoOut, PersonaIn, PersonaOut, PJIn, PJOut

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
        session, persona, descripcion=payload.descripcion
    )


@router.get("/{persona_id}/dm/juegos", response_model=list[JuegoOut])
async def listar_juegos_dm(
    persona_id: int, session: AsyncSession = Depends(get_session)
):
    """Juegos enlazados al perfil DM de la persona."""
    persona = await svc.get_persona(session, persona_id)
    if persona is None or persona.id_master is None:
        raise HTTPException(status_code=404, detail="Persona o perfil DM no encontrado")
    return await juegos_svc.list_juegos_for_dm(session, persona.id_master)


@router.post(
    "/{persona_id}/dm/juegos",
    response_model=JuegoOut,
    status_code=status.HTTP_200_OK,
)
async def añadir_juego_a_dm(
    persona_id: int,
    payload: DMJuegoIn,
    session: AsyncSession = Depends(get_session),
):
    """Enlaza un juego al DM. Si pasas `nombre` y no existe, se crea en catálogo."""
    persona = await svc.get_persona(session, persona_id)
    if persona is None or persona.id_master is None:
        raise HTTPException(status_code=404, detail="Persona o perfil DM no encontrado")

    if payload.id_juego is None and payload.nombre is None:
        raise HTTPException(
            status_code=422, detail="Pasa `id_juego` o `nombre`"
        )

    if payload.id_juego is not None:
        from tmjr.db.models import Juego  # local para evitar import circular
        juego = await session.get(Juego, payload.id_juego)
        if juego is None:
            raise HTTPException(status_code=404, detail="Juego no encontrado")
    else:
        juego, _ = await juegos_svc.get_or_create_juego(session, nombre=payload.nombre)

    await juegos_svc.add_juego_to_dm(
        session, id_dm=persona.id_master, id_juego=juego.id
    )
    return juego
