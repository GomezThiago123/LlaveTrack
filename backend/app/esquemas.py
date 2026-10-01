"""Formato de los datos que entran y salen de la API (validados con Pydantic).

En Python los campos van en snake_case (expira_en) y en el JSON en camelCase (expiraEn).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.modelos import EstadoLlave, EstadoReserva


class Esquema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class PedidoReserva(Esquema):
    aula_id: int


class ReservaSalida(Esquema):
    id: int
    aula: str
    codigo: str
    expira_en: datetime
    estado: EstadoReserva


class AulaPublica(Esquema):
    id: int
    nombre: str
    estado: EstadoLlave


class EstadoPublico(Esquema):
    equipo_online: bool
    aulas: list[AulaPublica]


class Tenedor(Esquema):
    """Quien tiene (o reservo) la llave. Solo lo ven preceptores y administradores."""

    nombre: str
    apellido: str
    telefono: str | None
    desde: datetime


class AulaDetalle(Esquema):
    id: int
    nombre: str
    estado: EstadoLlave
    tenedor: Tenedor | None = None
