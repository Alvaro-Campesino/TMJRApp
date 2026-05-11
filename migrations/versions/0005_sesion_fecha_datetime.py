"""sesion: cambia fecha de Date a DateTime

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-10

Cambios:
- sesion.fecha: Date → DateTime. Las sesiones ahora guardan día y hora
  en una sola columna. Las filas existentes se convierten a las 00:00
  del mismo día con `fecha::timestamp` (cast nativo de Postgres).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "sesion",
        "fecha",
        type_=sa.DateTime(),
        existing_type=sa.Date(),
        existing_nullable=False,
        postgresql_using="fecha::timestamp",
    )


def downgrade() -> None:
    op.alter_column(
        "sesion",
        "fecha",
        type_=sa.Date(),
        existing_type=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="fecha::date",
    )
