"""pj: elimina id_anfitrion; los invitados pasan a SesionPJ.acompanantes

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-11

Cambios:
- Borra de sesion_pj las filas cuyo id_pj corresponde a un PJ invitado
  (PJ.id_anfitrion IS NOT NULL) — esas filas quedan sin sentido en el
  nuevo modelo, donde los invitados se cuentan en sesion_pj.acompanantes
  de la fila del anfitrión.
- Borra los PJ invitados huérfanos.
- Drop FK fk_pj_id_anfitrion + columna pj.id_anfitrion.

downgrade recrea la columna y la FK pero NO restaura datos (los
invitados antiguos se perdieron en upgrade — no hay forma de
reconstruirlos a partir de acompanantes, que es un contador anónimo).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM sesion_pj WHERE id_pj IN "
        "(SELECT id FROM pj WHERE id_anfitrion IS NOT NULL)"
    )
    op.execute("DELETE FROM pj WHERE id_anfitrion IS NOT NULL")
    op.drop_constraint("fk_pj_id_anfitrion", "pj", type_="foreignkey")
    op.drop_column("pj", "id_anfitrion")


def downgrade() -> None:
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
