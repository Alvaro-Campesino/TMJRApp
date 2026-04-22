from fastapi import HTTPException, APIRouter
from models.aventura import Aventura, AventuraUpdate
from .base import *

router = APIRouter()
table_name = "Aventura"


@router.get("/aventura")
async def leer_aventuras(limit: int = 10, offset: int = 0):
    aventura = (
        supabase.table(table_name).select("*").limit(limit).offset(offset).execute()
    )
    return aventura


@router.post("/aventura/create")
async def crear_aventura(aventura: Aventura):
    data = aventura.model_dump(exclude="id")
    try:
        response = supabase.table(table_name).insert(data).execute()
        return response
    except Exception as error:
        raise HTTPException(status_code=500, detail="Ocurrió un error")


@router.post("/aventura/update/{id}")
async def editar_aventura(id: int, aventura: AventuraUpdate):
    check_exists(id)
    try:
        supabase.table(table_name).update(aventura.model_dump(exclude_unset=True)).eq(
            "id", id
        ).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail="No se pudo actualizar")
    return f"{table_name} se ha actualizado"


@router.delete("/aventura/delete/{id}")
async def borrar_aventura(id: int):
    check_exists(id)
    try:
        supabase.table(table_name).delete().eq("id", id).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail="No se pudo borrar")
    return f"{table_name} se ha borrado"


@router.get("/aventura/{id}")
async def leer_aventura(id: int):
    aventura = get(id, table_name)
    if is_empty(aventura):
        not_found()
    return Aventura(**aventura.data[0])
