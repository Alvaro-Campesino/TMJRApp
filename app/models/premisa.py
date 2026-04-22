from pydantic import BaseModel


class Premisa(BaseModel):
    id: int
    created_at: str
    titulo: str
    sistema: str | None = None
    descripcion: str | None = None
    aviso_contenido: str | None = None
    id_master: int


class PremisaUpdate(Premisa):
    created_at: str | None = None
    titulo: str | None = None
    id_master: int | None = None
