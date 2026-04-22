from pydantic import BaseModel


class Aventura(BaseModel):
    id: int
    created_at: str
    lugar: str
    plazas_totales: int
    plazas_sin_reserva: int
    plazas_ocupadas: int
    abierta_inscripcion: bool | None = None
    id_premisa: int


class AventuraUpdate(Aventura):
    lugar: str | None = None
    plazas_totales: int | None = None
    plazas_sin_reserva: int | None = None
    plazas_ocupadas: int | None = None
    id_premisa: int | None = None
