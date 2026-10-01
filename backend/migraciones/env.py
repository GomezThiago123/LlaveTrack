"""Configuracion de Alembic: usa la misma base y las mismas tablas que la aplicacion."""

from logging.config import fileConfig

from alembic import context

import app.modelos  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.db import Base, engine

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)


def correr_migraciones() -> None:
    with engine.connect() as conexion:
        context.configure(
            connection=conexion,
            target_metadata=Base.metadata,
            # SQLite no sabe modificar columnas: Alembic recrea la tabla cuando hace falta
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


correr_migraciones()
