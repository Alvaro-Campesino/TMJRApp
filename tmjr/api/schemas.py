from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PersonaIn(BaseModel):
    telegram_id: int
    nombre: str = Field(min_length=1, max_length=100)


class PersonaOut(_ORM):
    id: int
    telegram_id: int
    nombre: str
    id_pj: int | None
    id_master: int | None
    aceptada_normas: bool
    created_at: datetime


class DMIn(BaseModel):
    biografia: str | None = None


class DMOut(_ORM):
    id: int
    biografia: str | None
    created_at: datetime


class PJIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = None


class PJOut(_ORM):
    id: int
    nombre: str
    descripcion: str | None
    created_at: datetime


class SesionIn(BaseModel):
    id_dm: int
    id_juego: int                      # required: toda sesión tiene sistema
    fecha: datetime
    plazas_totales: int = Field(default=5, ge=1, le=6)
    plazas_sin_reserva: int = Field(default=1, ge=0)
    nombre: str | None = Field(default=None, max_length=100)
    descripcion: str | None = Field(default=None, max_length=400)
    id_premisa: int | None = None
    id_campania: int | None = None
    numero: int | None = None


class SesionOut(_ORM):
    id: int
    id_dm: int
    id_juego: int | None
    fecha: datetime
    plazas_totales: int
    plazas_sin_reserva: int
    nombre: str | None
    descripcion: str | None
    id_premisa: int | None
    id_campania: int | None
    numero: int | None
    telegram_chat_id: str | None
    telegram_thread_id: int | None
    telegram_message_id: int | None
    created_at: datetime


class ApuntarseIn(BaseModel):
    id_pj: int
    acompanantes: int = Field(default=0, ge=0, le=5)


class SesionPJOut(_ORM):
    id: int
    id_sesion: int
    id_pj: int
    acompanantes: int
    apuntada_en: datetime


class JuegoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = None


class JuegoOut(_ORM):
    id: int
    nombre: str
    descripcion: str | None
    created_at: datetime


class DMJuegoIn(BaseModel):
    """Añadir juego a un DM. Pasa id_juego (existente) o nombre (crea/busca)."""
    id_juego: int | None = None
    nombre: str | None = Field(default=None, min_length=1, max_length=100)


class PremisaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    id_juego: int | None = None
    descripcion: str | None = Field(default=None, max_length=400)
    aviso_contenido: str | None = Field(default=None, max_length=200)


class PremisaOut(_ORM):
    id: int
    nombre: str
    id_juego: int | None
    descripcion: str | None
    aviso_contenido: str | None
    created_at: datetime
