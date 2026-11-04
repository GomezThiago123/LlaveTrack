"""credencial (DNI), devolucion de terceros y modo alta (US-18, US-20, US-10)

Revision ID: a831fc0029a7
Revises: 6fb7f9b58f5a
Create Date: 2026-11-04 15:28:49.117772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.tipos


# revision identifiers, used by Alembic.
revision: str = 'a831fc0029a7'
down_revision: Union[str, Sequence[str], None] = '6fb7f9b58f5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('dispositivo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ultimo_tag_uid', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('ultimo_tag_slot', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ultimo_tag_en', app.tipos.FechaUTC(), nullable=True))

    with op.batch_alter_table('prestamo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('devuelto_por_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_prestamo_devuelto_por', 'usuario', ['devuelto_por_id'], ['id'])

    # usuario: sin batch (en SQLite recrearia la tabla y muchas tablas la referencian). El DNI unico
    # es un indice unico: varios null no chocan
    op.add_column('usuario', sa.Column('dni', sa.String(length=10), nullable=True))
    op.create_index('ix_usuario_dni', 'usuario', ['dni'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_usuario_dni', table_name='usuario')
    op.drop_column('usuario', 'dni')

    with op.batch_alter_table('prestamo', schema=None) as batch_op:
        batch_op.drop_constraint('fk_prestamo_devuelto_por', type_='foreignkey')
        batch_op.drop_column('devuelto_por_id')

    with op.batch_alter_table('dispositivo', schema=None) as batch_op:
        batch_op.drop_column('ultimo_tag_en')
        batch_op.drop_column('ultimo_tag_slot')
        batch_op.drop_column('ultimo_tag_uid')
