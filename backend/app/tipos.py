from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


def ahora_utc() -> datetime:
    """Hora actual en UTC. Todas las horas del sistema las pone el servidor."""
    return datetime.now(UTC)


class FechaUTC(TypeDecorator):
    """Fecha y hora guardada siempre en UTC.

    SQLite no guarda la zona horaria: este tipo convierte a UTC al guardar y le vuelve
    a poner la zona UTC al leer, para no mezclar horas con y sin zona.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, valor: datetime | None, dialect):
        if valor is None:
            return None
        if valor.tzinfo is None:
            raise ValueError("Las fechas tienen que tener zona horaria (usar ahora_utc())")
        return valor.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, valor: datetime | None, dialect):
        if valor is None:
            return None
        return valor.replace(tzinfo=UTC)
