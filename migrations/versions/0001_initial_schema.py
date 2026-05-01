"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "juegos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(100), nullable=False, unique=True),
        sa.Column("descripcion", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "dm",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("biografia", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "pj",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("descripcion", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "personas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("id_pj", sa.Integer(), sa.ForeignKey("pj.id"), unique=True),
        sa.Column("id_master", sa.Integer(), sa.ForeignKey("dm.id"), unique=True),
        sa.Column("filtro_contenido", postgresql.JSONB()),
        sa.Column("aceptada_normas", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "premisa",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("id_juego", sa.Integer(), sa.ForeignKey("juegos.id")),
        sa.Column("descripcion", sa.String(400)),
        sa.Column("aviso_contenido", sa.String(200)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "campania",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_premisa", sa.Integer(), sa.ForeignKey("premisa.id"), nullable=False),
        sa.Column("id_dm", sa.Integer(), sa.ForeignKey("dm.id"), nullable=False),
        sa.Column("periodicidad", sa.String(20)),
        sa.Column("plazas", sa.Integer()),
        sa.Column("fecha_inicio", sa.Date()),
        sa.Column("finalizada", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("cancelada", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "sesion",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_premisa", sa.Integer(), sa.ForeignKey("premisa.id")),
        sa.Column("id_campania", sa.Integer(), sa.ForeignKey("campania.id")),
        sa.Column("id_dm", sa.Integer(), sa.ForeignKey("dm.id"), nullable=False),
        sa.Column("numero", sa.Integer()),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("plazas_totales", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("plazas_sin_reserva", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("telegram_chat_id", sa.String(64)),
        sa.Column("telegram_thread_id", sa.Integer()),
        sa.Column("telegram_message_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("id_premisa", "numero", name="uq_sesion_premisa_numero"),
    )
    op.create_index("ix_sesion_fecha", "sesion", ["fecha"])
    op.create_index("ix_sesion_id_campania", "sesion", ["id_campania"])

    op.create_table(
        "dm_juegos",
        sa.Column("id_dm", sa.Integer(), sa.ForeignKey("dm.id"), primary_key=True),
        sa.Column("id_juego", sa.Integer(), sa.ForeignKey("juegos.id"), primary_key=True),
    )

    op.create_table(
        "dm_premisas",
        sa.Column("id_dm", sa.Integer(), sa.ForeignKey("dm.id"), primary_key=True),
        sa.Column("id_premisa", sa.Integer(), sa.ForeignKey("premisa.id"), primary_key=True),
    )

    op.create_table(
        "pj_juegos_preferidos",
        sa.Column("id_pj", sa.Integer(), sa.ForeignKey("pj.id"), primary_key=True),
        sa.Column("id_juego", sa.Integer(), sa.ForeignKey("juegos.id"), primary_key=True),
    )

    op.create_table(
        "pj_juegos_conocidos",
        sa.Column("id_pj", sa.Integer(), sa.ForeignKey("pj.id"), primary_key=True),
        sa.Column("id_juego", sa.Integer(), sa.ForeignKey("juegos.id"), primary_key=True),
    )

    op.create_table(
        "campania_pjs_fijos",
        sa.Column("id_campania", sa.Integer(), sa.ForeignKey("campania.id"), primary_key=True),
        sa.Column("id_pj", sa.Integer(), sa.ForeignKey("pj.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "sesion_pj",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_sesion", sa.Integer(), sa.ForeignKey("sesion.id"), nullable=False),
        sa.Column("id_pj", sa.Integer(), sa.ForeignKey("pj.id"), nullable=False),
        sa.Column("acompanantes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("apuntada_en", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("id_sesion", "id_pj", name="uq_sesion_pj"),
    )
    op.create_index("ix_sesion_pj_sesion", "sesion_pj", ["id_sesion"])

    op.create_table(
        "pjs_en_espera",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_pj", sa.Integer(), sa.ForeignKey("pj.id"), nullable=False),
        sa.Column("id_sesion", sa.Integer(), sa.ForeignKey("sesion.id"), nullable=False),
        sa.Column("asistencia_segura", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("id_pj", "id_sesion", name="uq_pj_espera_sesion"),
    )
    op.create_index("ix_pjs_en_espera_sesion", "pjs_en_espera", ["id_sesion"])

    op.create_table(
        "limites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("palabra_clave", sa.String()),
        sa.Column("descripcion", sa.String()),
    )

    op.create_table(
        "limites_sesion",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_sesion", sa.Integer(), sa.ForeignKey("sesion.id")),
        sa.Column("id_limite", sa.Integer(), sa.ForeignKey("limites.id")),
    )


def downgrade() -> None:
    for table in (
        "limites_sesion",
        "limites",
        "pjs_en_espera",
        "sesion_pj",
        "campania_pjs_fijos",
        "pj_juegos_conocidos",
        "pj_juegos_preferidos",
        "dm_premisas",
        "dm_juegos",
        "sesion",
        "campania",
        "premisa",
        "personas",
        "pj",
        "dm",
        "juegos",
    ):
        op.drop_table(table)
