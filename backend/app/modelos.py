"""Tablas de la base de datos (ver "Modelo de datos" en CLAUDE.md)."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.tipos import FechaUTC, ahora_utc


class Rol(StrEnum):
    DOCENTE = "DOCENTE"
    PRECEPTOR = "PRECEPTOR"
    ADMIN = "ADMIN"


class EstadoLlave(StrEnum):
    DISPONIBLE = "DISPONIBLE"
    RESERVADA = "RESERVADA"
    PRESTADA = "PRESTADA"
    BAJA = "BAJA"


class EstadoReserva(StrEnum):
    PENDIENTE = "PENDIENTE"
    USADA = "USADA"
    VENCIDA = "VENCIDA"
    CANCELADA = "CANCELADA"


def _enum(clase):
    # Se guarda como texto (no como tipo ENUM de la base) para que funcione igual en SQLite y PostgreSQL
    return Enum(clase, native_enum=False, length=20)


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    apellido: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    telefono: Mapped[str | None] = mapped_column(String(30))
    rol: Mapped[Rol] = mapped_column(_enum(Rol))
    activo: Mapped[bool] = mapped_column(default=True)

    # Autenticacion (se usan en la Fase 2)
    password_hash: Mapped[str | None] = mapped_column(String(100))  # null = solo entra con Google
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    intentos_fallidos: Mapped[int] = mapped_column(default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(FechaUTC)


class Aula(Base):
    __tablename__ = "aula"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(40), unique=True)

    llaves: Mapped[list["Llave"]] = relationship(back_populates="aula")


class Llave(Base):
    __tablename__ = "llave"

    id: Mapped[int] = mapped_column(primary_key=True)
    aula_id: Mapped[int] = mapped_column(ForeignKey("aula.id"))
    rfid_uid: Mapped[str] = mapped_column(String(20), unique=True)  # hex en mayusculas, sin separadores
    slot: Mapped[int | None]  # posicion actual en el disco; null mientras esta prestada
    estado: Mapped[EstadoLlave] = mapped_column(_enum(EstadoLlave), default=EstadoLlave.DISPONIBLE)

    aula: Mapped[Aula] = relationship(back_populates="llaves")


class Reserva(Base):
    __tablename__ = "reserva"
    __table_args__ = (
        # Indices unicos "parciales": solo cuentan las reservas PENDIENTES.
        # Son la ultima barrera en la base; las reglas tambien se controlan en app/servicios.
        Index(
            "ix_reserva_codigo_pendiente",
            "codigo",
            unique=True,
            sqlite_where=text("estado = 'PENDIENTE'"),
            postgresql_where=text("estado = 'PENDIENTE'"),
        ),
        Index(
            "ix_reserva_usuario_pendiente",
            "usuario_id",
            unique=True,
            sqlite_where=text("estado = 'PENDIENTE'"),
            postgresql_where=text("estado = 'PENDIENTE'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    llave_id: Mapped[int] = mapped_column(ForeignKey("llave.id"))
    codigo: Mapped[str] = mapped_column(String(6))
    creada_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)
    expira_en: Mapped[datetime] = mapped_column(FechaUTC)
    estado: Mapped[EstadoReserva] = mapped_column(
        _enum(EstadoReserva), default=EstadoReserva.PENDIENTE
    )

    usuario: Mapped[Usuario] = relationship()
    llave: Mapped[Llave] = relationship()


class Prestamo(Base):
    __tablename__ = "prestamo"

    id: Mapped[int] = mapped_column(primary_key=True)
    llave_id: Mapped[int] = mapped_column(ForeignKey("llave.id"))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    reserva_id: Mapped[int] = mapped_column(ForeignKey("reserva.id"))
    retirado_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)
    devuelto_en: Mapped[datetime | None] = mapped_column(FechaUTC)  # null = prestamo activo

    usuario: Mapped[Usuario] = relationship()
    llave: Mapped[Llave] = relationship()


class Dispositivo(Base):
    __tablename__ = "dispositivo"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(String(40), unique=True)  # ej. "equipo-01"
    slots_totales: Mapped[int]
    slots_reservados: Mapped[list[int]] = mapped_column(JSON, default=list)  # nunca llevan llave
    online: Mapped[bool] = mapped_column(default=False)
    ultimo_contacto: Mapped[datetime | None] = mapped_column(FechaUTC)


class EventoDispositivo(Base):
    """Log de todo lo que manda el equipo. El eventId unico sirve para descartar duplicados."""

    __tablename__ = "evento_dispositivo"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(80), unique=True)
    device_id: Mapped[str] = mapped_column(String(40))
    tipo: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    respuesta: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # se reenvia si llega repetido
    recibido_en: Mapped[datetime] = mapped_column(FechaUTC, default=ahora_utc)
