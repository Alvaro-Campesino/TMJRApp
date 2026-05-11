"""pj: añade columna id_anfitrion para PJs invitados (sin Telegram)

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-11

Cambios:
- pj.id_anfitrion (integer, NULL, FK pj.id ON DELETE SET NULL):
  Si no es NULL, el PJ es un "invitado" creado por otro PJ con el botón
  +1 en la tarjeta de una sesión. El nombre del invitado se compone como
  "Invitado <nombre del anfitrión>". Permite cubrir personas sin Telegram
  que vienen acompañando a alguien apuntado.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pj",
        sa.Column("id_anfitrion", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pj_id_anfitrion",
        source_table="pj",
        referent_table="pj",
        local_cols=["id_anfitrion"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_pj_id_anfitrion", "pj", type_="foreignkey")
    op.drop_column("pj", "id_anfitrion")
