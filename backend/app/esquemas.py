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
    # US-16: hasta que hora va a usar el aula, "HH:MM" en hora de Argentina (opcional)
    hora_fin: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class ReservaSalida(Esquema):
    id: int
    aula: str
    codigo: str
    creada_en: datetime  # la web la usa para la barra de tiempo
    expira_en: datetime
    estado: EstadoReserva
    hora_fin: datetime | None = None  # US-16


# El estado que ve la web: el de la llave, o EN_REVISION si su aula tiene un incidente abierto (US-21)
EstadoAula = EstadoLlave | Literal["EN_REVISION"]


class AulaPublica(Esquema):
    id: int
    nombre: str
    estado: EstadoAula


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
    estado: EstadoAula
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
    perdida: bool = False  # US-11: se cerro porque la llave se perdio
    hora_fin: datetime | None = None  # US-16: hasta que hora dijo que usaba el aula
    aviso_automatico_en: datetime | None = None  # US-16: el mail de los 15 minutos
    demorada: bool = False  # US-16: sigue sin devolver una hora despues de la hora fin


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
    # Donde quedo colgada en el disco. Obligatorio para reponer una llave dada de baja (US-11)
    slot: int | None = Field(default=None, ge=0)


class PedidoBaja(Esquema):
    """US-11: por que se da de baja (ej. \"Se perdio en el aula\")."""

    motivo: str = Field(min_length=3, max_length=200)


class BajaSalida(Esquema):
    id: int
    aula: str
    rfid_uid: str  # el tag que tenia la llave perdida
    motivo: str
    dada_en: datetime
    ultimo_docente: str | None  # "Ana Perez", o null si nunca se presto
    preceptor: str  # quien la dio de baja


class IncidenteSalida(Esquema):
    id: int
    ocurrido_en: datetime
    tipo: str  # LLAVE_NO_ENCONTRADA, MOTOR_NO_GIRA, ...
    descripcion: str  # para mostrar: "Llave no encontrada"
    aula: str | None
    docente: str | None  # "Ana Perez"
    detalle: str | None
    resuelto_en: datetime | None = None  # US-21: null = abierto
    resuelto_por: str | None = None  # "Carla Diaz"


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
