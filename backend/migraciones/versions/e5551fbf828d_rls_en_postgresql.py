"""RLS en PostgreSQL (Supabase)

Supabase publica sola, por su propia API REST, toda tabla del esquema public.
Activando RLS sin ninguna politica, esa API no ve ni modifica nada.
El servidor entra como dueno de las tablas (usuario postgres), y RLS no se aplica al dueno.
En SQLite no hace nada.

Toda tabla nueva tiene que activar RLS en su propia migracion.

Revision ID: e5551fbf828d
Revises: 6d0fa4761c3f
Create Date: 2026-10-20 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.tipos


# revision identifiers, used by Alembic.
revision: str = 'e5551fbf828d'
down_revision: Union[str, Sequence[str], None] = '6d0fa4761c3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLAS = (
    "alembic_version",
    "usuario",
    "sesion",
    "recuperacion_clave",
    "aula",
    "llave",
    "reserva",
    "prestamo",
    "dispositivo",
    "evento_dispositivo",
)


def upgrade() -> None:
    """Upgrade schema."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Downgrade schema."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY")
