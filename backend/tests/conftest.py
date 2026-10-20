"""Configuracion compartida de los tests.

Cada test usa una base SQLite nueva en una carpeta temporal, cargada con seed/datos.json.
Nunca toca backend/llavetrack.db.
"""

import json
import os

# Antes de importar la app: hashes de contrasena baratos, para que los tests vayan rapido
os.environ["BCRYPT_RONDAS"] = "4"

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



CLAVE_DE_PRUEBA = "llavetrack"  # la de seed/datos.json


@pytest.fixture
def ingresar(cliente):
    """Hace login con el cliente de test: desde ahi manda la cookie de sesion en cada pedido.

    Uso: ingresar("ana.perez@example.com")
    """

    def _ingresar(email: str, clave: str = CLAVE_DE_PRUEBA):
        res = cliente.post("/api/auth/login", json={"email": email, "clave": clave})
        assert res.status_code == 200, res.text
        return res

    return _ingresar
