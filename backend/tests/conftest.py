"""Configuracion compartida de los tests.

Cada test usa una base SQLite nueva en una carpeta temporal, cargada con seed/datos.json.
Nunca toca backend/llavetrack.db.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import Base, crear_engine, obtener_sesion
from app.main import app
from app.seed import ARCHIVO_DATOS, cargar_datos


@pytest.fixture
def fabrica_sesiones(tmp_path):
    """Devuelve un sessionmaker conectado a una base temporal con los datos del seed."""
    engine = crear_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(engine, expire_on_commit=False)
    with fabrica() as sesion:
        cargar_datos(sesion, json.loads(ARCHIVO_DATOS.read_text(encoding="utf-8")))
        sesion.commit()
    yield fabrica
    engine.dispose()


@pytest.fixture
def sesion(fabrica_sesiones):
    with fabrica_sesiones() as s:
        yield s


@pytest.fixture
def cliente(fabrica_sesiones):
    """Cliente HTTP de la API usando la base temporal."""

    def sesion_de_test():
        with fabrica_sesiones() as s:
            yield s

    app.dependency_overrides[obtener_sesion] = sesion_de_test
    yield TestClient(app)
    app.dependency_overrides.clear()
