from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import config


class Base(DeclarativeBase):
    """Clase base de todas las tablas (ver app/modelos.py)."""


def crear_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url)

    # check_same_thread=False: FastAPI y el cliente MQTT usan la base desde varios hilos
    # timeout=10: si otro pedido esta escribiendo, espera hasta 10 s en lugar de fallar
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 10})

    @event.listens_for(engine, "connect")
    def _al_conectar(conexion_sqlite, _registro):
        # Dejamos que SQLAlchemy maneje las transacciones (no el modulo sqlite3)
        conexion_sqlite.isolation_level = None
        conexion_sqlite.execute("PRAGMA foreign_keys = ON")

    @event.listens_for(engine, "begin")
    def _al_empezar(conexion):
        # BEGIN IMMEDIATE toma el permiso de escritura al empezar la transaccion.
        # Asi dos pedidos simultaneos se ponen en fila en vez de chocar a mitad de camino.
        # Consecuencia: mientras una sesion este abierta, las demas esperan. Toda sesion
        # tiene que cerrarse rapido (una por pedido HTTP o por evento MQTT, nunca global).
        conexion.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


engine = crear_engine(config.database_url)
SesionLocal = sessionmaker(engine, expire_on_commit=False)


def obtener_sesion():
    """Dependencia de FastAPI: una sesion por pedido HTTP.

    Las rutas hacen commit al terminar bien. Si algo falla, al cerrar la sesion
    se deshace todo lo que no se confirmo.
    """
    with SesionLocal() as sesion:
        yield sesion


__all__ = ["Base", "Session", "SesionLocal", "crear_engine", "engine", "obtener_sesion"]
