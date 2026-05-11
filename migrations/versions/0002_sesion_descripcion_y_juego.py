"""sesion: añade nombre, descripcion y id_juego

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-02

Cambios:
- sesion.nombre (varchar 100, NULL): nombre de esta sesión concreta. El bot
  típicamente lo copia de premisa.nombre al crear, pero puede divergir
  (p.ej. "Strahd — Episodio 3").
- sesion.descripcion (varchar 400, NULL): nota opcional específica de esta sesión.
  El bot la usa en el publicador como override de premisa.descripcion.
- sesion.id_juego (integer, NULL, FK juegos.id): sistema de rol concreto de la
  sesión. En BD queda NULL para no romper sesiones ya existentes; el código
  Python (Pydantic SesionIn) lo exige obligatorio para nuevas creaciones.
  Posible migración futura: ALTER COLUMN ... SET NOT NULL cuando todas las
  filas estén pobladas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sesion",
        sa.Column("nombre", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "sesion",
        sa.Column("descripcion", sa.String(length=400), nullable=True),
    )
    op.add_column(
        "sesion",
        sa.Column("id_juego", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_sesion_id_juego",
        source_table="sesion",
        referent_table="juegos",
        local_cols=["id_juego"],
        remote_cols=["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_sesion_id_juego", "sesion", type_="foreignkey")
    op.drop_column("sesion", "id_juego")
    op.drop_column("sesion", "descripcion")
    op.drop_column("sesion", "nombre")
