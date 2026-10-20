"""Formato de los datos que entran y salen de la API (validados con Pydantic).

En Python los campos van en snake_case (expira_en) y en el JSON en camelCase (expiraEn).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.modelos import EstadoLlave, EstadoReserva, Rol
from app.servicios.auth import CLAVE_MAX_BYTES


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


# --- Login (US-01, US-07, US-08) ---


class PedidoLogin(Esquema):
    email: str = Field(max_length=120)
    clave: str = Field(max_length=200)


class UsuarioSalida(Esquema):
    id: int
    nombre: str
    apellido: str
    email: str
    rol: Rol


class PedidoRecuperacion(Esquema):
    email: str = Field(max_length=120)


class PedidoRestablecer(Esquema):
    token: str = Field(max_length=100)
    clave_nueva: str = Field(min_length=8)

    @field_validator("clave_nueva")
    @classmethod
    def no_muy_larga(cls, clave: str) -> str:
        if len(clave.encode()) > CLAVE_MAX_BYTES:
            raise ValueError(f"la contraseña puede tener hasta {CLAVE_MAX_BYTES} caracteres")
        return clave


class Mensaje(Esquema):
    mensaje: str
