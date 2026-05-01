"""ORM models. Espejo de schema.dbml — esa es la fuente de verdad."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Portable JSON: usa JSONB en Postgres, JSON genérico en otros dialectos (SQLite, etc.).
JsonCol = JSON().with_variant(JSONB(), "postgresql")

from .session import Base


class Juego(Base):
    __tablename__ = "juegos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DM(Base):
    __tablename__ = "dm"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    biografia: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DMJuego(Base):
    __tablename__ = "dm_juegos"

    id_dm: Mapped[int] = mapped_column(ForeignKey("dm.id"), primary_key=True)
    id_juego: Mapped[int] = mapped_column(ForeignKey("juegos.id"), primary_key=True)


class DMPremisa(Base):
    __tablename__ = "dm_premisas"

    id_dm: Mapped[int] = mapped_column(ForeignKey("dm.id"), primary_key=True)
    id_premisa: Mapped[int] = mapped_column(ForeignKey("premisa.id"), primary_key=True)


class PJ(Base):
    __tablename__ = "pj"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PJJuegoPreferido(Base):
    __tablename__ = "pj_juegos_preferidos"

    id_pj: Mapped[int] = mapped_column(ForeignKey("pj.id"), primary_key=True)
    id_juego: Mapped[int] = mapped_column(ForeignKey("juegos.id"), primary_key=True)


class PJJuegoConocido(Base):
    __tablename__ = "pj_juegos_conocidos"

    id_pj: Mapped[int] = mapped_column(ForeignKey("pj.id"), primary_key=True)
    id_juego: Mapped[int] = mapped_column(ForeignKey("juegos.id"), primary_key=True)


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    id_pj: Mapped[int | None] = mapped_column(ForeignKey("pj.id"), unique=True)
    id_master: Mapped[int | None] = mapped_column(ForeignKey("dm.id"), unique=True)
    filtro_contenido: Mapped[dict | None] = mapped_column(JsonCol)
    aceptada_normas: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    pj: Mapped[PJ | None] = relationship(foreign_keys=[id_pj], lazy="joined")
    dm: Mapped[DM | None] = relationship(foreign_keys=[id_master], lazy="joined")


class Limite(Base):
    __tablename__ = "limites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    palabra_clave: Mapped[str | None] = mapped_column(String)
    descripcion: Mapped[str | None] = mapped_column(String)


class LimiteSesion(Base):
    __tablename__ = "limites_sesion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_sesion: Mapped[int | None] = mapped_column(ForeignKey("sesion.id"))
    id_limite: Mapped[int | None] = mapped_column(ForeignKey("limites.id"))


class Premisa(Base):
    __tablename__ = "premisa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    id_juego: Mapped[int | None] = mapped_column(ForeignKey("juegos.id"))
    descripcion: Mapped[str | None] = mapped_column(String(400))
    aviso_contenido: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Campania(Base):
    __tablename__ = "campania"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_premisa: Mapped[int] = mapped_column(ForeignKey("premisa.id"), nullable=False)
    id_dm: Mapped[int] = mapped_column(ForeignKey("dm.id"), nullable=False)
    periodicidad: Mapped[str | None] = mapped_column(String(20))
    plazas: Mapped[int | None] = mapped_column(Integer)
    fecha_inicio: Mapped[date | None] = mapped_column(Date)
    finalizada: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    cancelada: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CampaniaPJFijo(Base):
    __tablename__ = "campania_pjs_fijos"

    id_campania: Mapped[int] = mapped_column(ForeignKey("campania.id"), primary_key=True)
    id_pj: Mapped[int] = mapped_column(ForeignKey("pj.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Sesion(Base):
    __tablename__ = "sesion"
    __table_args__ = (
        UniqueConstraint("id_premisa", "numero", name="uq_sesion_premisa_numero"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_premisa: Mapped[int | None] = mapped_column(ForeignKey("premisa.id"))
    id_campania: Mapped[int | None] = mapped_column(ForeignKey("campania.id"))
    id_dm: Mapped[int] = mapped_column(ForeignKey("dm.id"), nullable=False)
    numero: Mapped[int | None] = mapped_column(Integer)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    plazas_totales: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    plazas_sin_reserva: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64))
    telegram_thread_id: Mapped[int | None] = mapped_column(Integer)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SesionPJ(Base):
    __tablename__ = "sesion_pj"
    __table_args__ = (
        UniqueConstraint("id_sesion", "id_pj", name="uq_sesion_pj"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_sesion: Mapped[int] = mapped_column(ForeignKey("sesion.id"), nullable=False)
    id_pj: Mapped[int] = mapped_column(ForeignKey("pj.id"), nullable=False)
    acompanantes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    apuntada_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PJEnEspera(Base):
    __tablename__ = "pjs_en_espera"
    __table_args__ = (
        UniqueConstraint("id_pj", "id_sesion", name="uq_pj_espera_sesion"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_pj: Mapped[int] = mapped_column(ForeignKey("pj.id"), nullable=False)
    id_sesion: Mapped[int] = mapped_column(ForeignKey("sesion.id"), nullable=False)
    asistencia_segura: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
