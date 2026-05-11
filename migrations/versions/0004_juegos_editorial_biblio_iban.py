"""juegos: añade editorial, disponible_en_biblioteca, iban

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-10

Cambios:
- juegos.editorial (varchar 100, NULL): editorial / publisher.
- juegos.disponible_en_biblioteca (boolean, NOT NULL, default false):
  marca si el juego está disponible para préstamo en la biblioteca.
- juegos.iban (varchar 34, NULL): IBAN asociado al juego (p.ej. para
  apuntarse al pago colectivo del manual). Longitud máxima IBAN = 34.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "juegos",
        sa.Column("editorial", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "juegos",
        sa.Column(
            "disponible_en_biblioteca",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "juegos",
        sa.Column("iban", sa.String(length=34), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("juegos", "iban")
    op.drop_column("juegos", "disponible_en_biblioteca")
    op.drop_column("juegos", "editorial")
