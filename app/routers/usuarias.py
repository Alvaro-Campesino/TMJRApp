from fastapi import HTTPException, APIRouter
from models.usuaria import Usuaria, UsuariaUpdate, random_user_gender
from .base import *

router = APIRouter()
table_name = "Usuaria"


@router.get("/usuaria")
async def leer_usuarias(limit: int = 10, offset: int = 0):
    usuaria = (
        supabase.table(table_name)
        .select("id, filtro_contenido, peticion")
        .limit(limit)
        .offset(offset)
        .execute()
    )
    return usuaria


@router.post("/usuaria/create")
async def crear_usuaria(usuaria: Usuaria):
    data = usuaria.model_dump(exclude="id")
    try:
        response = supabase.table(table_name).insert(data).execute()
        return response
    except Exception as error:
        if error.code == "23505":
            raise HTTPException(status_code=500, detail="Ese id de telegram ya existe")
        else:
            raise HTTPException(status_code=500, detail="Ocurrió un error")


@router.post("/usuaria/update/{id}")
async def editar_usuaria(id: int, usuaria: UsuariaUpdate):
    check_exists(id, table_name)
    try:
        supabase.table(table_name).update(usuaria.model_dump(exclude_unset=True)).eq(
            "id", id
        ).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail="No se pudo actualizar")
    return f"{random_user_gender()} se ha actualizado"


@router.delete("/usuaria/delete/{id}")
async def borrar_usuaria(id: int):
    check_exists(id, table_name)
    try:
        supabase.table(table_name).delete().eq("id", id).execute()
    except Exception as error:
        raise HTTPException(status_code=500, detail="No se pudo borrar")
    return f"{random_user_gender()} se ha borrado"


@router.get("/usuaria/tgid/{tg}")
async def leer_usuaria_by_tgid(tg: str | None = None):
    usuaria = (
        supabase.table(table_name)
        .select("id, filtro_contenido, peticion")
        .eq("telegram_id", tg)
        .execute()
    )
    if usuaria is None or usuaria.data == []:
        raise HTTPException(
            status_code=404,
            detail=f"No hay {random_user_gender(False,False,True)} con id de telegram {tg}",
        )
    return usuaria


@router.get("/usuaria/{id}")
async def leer_usuaria(id: int):
    usuaria = get(id, table_name)
    if is_empty(usuaria):
        not_found()
    return Usuaria(**usuaria.data[0])
