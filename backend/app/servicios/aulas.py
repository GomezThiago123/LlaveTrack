"""Consulta de aulas y disponibilidad de llaves (US-02)."""

from sqlalchemy import select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.esquemas import AulaDetalle, AulaPublica, EstadoPublico, Tenedor
from app.modelos import (
    Aula,
    EstadoLlave,
    EstadoReserva,
    Llave,
    Prestamo,
    Reserva,
    Usuario,
)
from app.servicios.conexion import equipo_online
from app.servicios.reservas import vencer_reservas

def _llaves_en_uso(sesion: Session) -> list[Llave]:
    """Una llave por aula (MVP), sin las dadas de baja, ordenadas por nombre de aula.

    contains_eager: el aula viene en la misma consulta. Sin eso, SQLAlchemy la pide aparte
    para cada llave (30 consultas mas); con Supabase lejos, eso son segundos.
    """
    return list(
        sesion.scalars(
            select(Llave)
            .join(Aula)
            .options(contains_eager(Llave.aula))
            .where(Llave.estado != EstadoLlave.BAJA)
            .order_by(Aula.nombre)
        )
    )


def estado_publico(sesion: Session) -> EstadoPublico:
    """Lo que se ve sin login: estado de cada aula y si el equipo esta online. Sin datos personales."""
    vencer_reservas(sesion)
    return EstadoPublico(
        equipo_online=equipo_online(sesion),
        aulas=[
            AulaPublica(id=llave.aula.id, nombre=llave.aula.nombre, estado=llave.estado)
            for llave in _llaves_en_uso(sesion)
        ],
    )


def aulas_con_tenedor(sesion: Session) -> list[AulaDetalle]:
    """Lista de aulas para cualquier usuario logueado, con quien tiene cada llave,
    desde que hora y su telefono (US-02: lo ven todos los roles)."""
    vencer_reservas(sesion)
    return [
        AulaDetalle(
            id=llave.aula.id,
            nombre=llave.aula.nombre,
            estado=llave.estado,
            tenedor=_tenedor(sesion, llave),
        )
        for llave in _llaves_en_uso(sesion)
    ]


def _tenedor(sesion: Session, llave: Llave) -> Tenedor | None:
    if llave.estado == EstadoLlave.PRESTADA:
        prestamo = sesion.scalar(
            select(Prestamo)
            .options(joinedload(Prestamo.usuario))
            .where(Prestamo.llave_id == llave.id, Prestamo.devuelto_en.is_(None))
        )
        if prestamo:
            return _datos_tenedor(prestamo.usuario, prestamo.retirado_en)
    if llave.estado == EstadoLlave.RESERVADA:
        reserva = sesion.scalar(
            select(Reserva)
            .options(joinedload(Reserva.usuario))
            .where(Reserva.llave_id == llave.id, Reserva.estado == EstadoReserva.PENDIENTE)
        )
        if reserva:
            return _datos_tenedor(reserva.usuario, reserva.creada_en)
    return None


def _datos_tenedor(usuario: Usuario, desde) -> Tenedor:
    return Tenedor(
        usuario_id=usuario.id,
        nombre=usuario.nombre,
        apellido=usuario.apellido,
        telefono=usuario.telefono,
        desde=desde,
    )
