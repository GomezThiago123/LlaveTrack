"""Formato de los datos que entran y salen de la API (validados con Pydantic).

En Python los campos van en snake_case (expira_en) y en el JSON en camelCase (expiraEn).
"""

from datetime import date, datetime
from typing import Literal

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
    """Quien tiene (o reservo) la llave (US-02: lo ven todos los usuarios logueados)."""

    usuario_id: int  # la web lo compara con el suyo para mostrar "En tu poder"
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
    telefono: str | None
    rol: Rol



class CuentaBloqueada(Esquema):
    id: int
    nombre: str
    apellido: str
    email: str
    bloqueado_hasta: datetime




# --- Prestamos (US-17, US-12/13, US-16) ---


class PersonaSalida(Esquema):
    id: int
    nombre: str
    apellido: str
    email: str
    telefono: str | None


class PrestamoSalida(Esquema):
    id: int
    aula: str
    docente: PersonaSalida
    retirado_en: datetime
    devuelto_en: datetime | None
    recordatorio_enviado_en: datetime | None


class HistorialSalida(Esquema):
    prestamos: list[PrestamoSalida]
    en_poder: int | None  # US-13: solo si se filtro por docente


class FiltrosHistorial(Esquema):
    aula_id: int | None = None
    usuario_id: int | None = None
    desde: date | None = None
    hasta: date | None = None
    estado: Literal["todos", "abiertos", "devueltos"] = "todos"


# --- Gestion de docentes (US-09) ---


class UsuarioDetalle(Esquema):
    id: int
    nombre: str
    apellido: str
    email: str
    telefono: str | None
    rol: Rol
    activo: bool
    tiene_clave: bool  # false = todavia no uso el link del mail de alta


class PedidoAlta(Esquema):
    nombre: str = Field(min_length=1, max_length=80)
    apellido: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    telefono: str | None = Field(default=None, max_length=30)


class PedidoActivo(Esquema):
    activo: bool


# --- Equipo y llaves (US-10) ---


class LlaveEquipo(Esquema):
    id: int
    aula: str
    rfid_uid: str
    slot: int | None  # null mientras esta prestada (no esta en el disco)
    estado: EstadoLlave


class EquipoSalida(Esquema):
    device_id: str | None  # null si el equipo nunca se conecto
    online: bool
    ultimo_contacto: datetime | None
    slots_totales: int
    slots_reservados: list[int]
    llaves: list[LlaveEquipo]


class PedidoRfid(Esquema):
    rfid_uid: str = Field(min_length=1, max_length=40)


class IncidenteSalida(Esquema):
    id: int
    ocurrido_en: datetime
    tipo: str  # LLAVE_NO_ENCONTRADA, MOTOR_NO_GIRA, ...
    descripcion: str  # para mostrar: "Llave no encontrada"
    aula: str | None
    docente: str | None  # "Ana Perez"
    detalle: str | None


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
