"""Consulta de aulas y disponibilidad de llaves (US-02)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.esquemas import AulaDetalle, AulaPublica, EstadoPublico, Tenedor
from app.modelos import (
    Aula,
    Dispositivo,
    EstadoLlave,
    EstadoReserva,
    Llave,
    Prestamo,
    Reserva,
    Rol,
    Usuario,
)
from app.servicios.reservas import vencer_reservas

ROLES_QUE_VEN_TENEDOR = {Rol.PRECEPTOR, Rol.ADMIN}


def _llaves_en_uso(sesion: Session) -> list[Llave]:
    """Una llave por aula (MVP), sin las dadas de baja, ordenadas por nombre de aula."""
    return list(
        sesion.scalars(
            select(Llave).join(Aula).where(Llave.estado != EstadoLlave.BAJA).order_by(Aula.nombre)
        )
    )


def estado_publico(sesion: Session) -> EstadoPublico:
    """Lo que se ve sin login: estado de cada aula y si el equipo esta online. Sin datos personales."""
    vencer_reservas(sesion)
    equipo_online = sesion.scalar(select(Dispositivo.id).where(Dispositivo.online)) is not None
    return EstadoPublico(
        equipo_online=equipo_online,
        aulas=[
            AulaPublica(id=llave.aula.id, nombre=llave.aula.nombre, estado=llave.estado)
            for llave in _llaves_en_uso(sesion)
        ],
    )


def aulas_para(sesion: Session, usuario: Usuario) -> list[AulaDetalle]:
    """Lista de aulas para un usuario logueado. Preceptor y admin ven quien tiene cada llave."""
    vencer_reservas(sesion)
    ve_tenedor = usuario.rol in ROLES_QUE_VEN_TENEDOR
    return [
        AulaDetalle(
            id=llave.aula.id,
            nombre=llave.aula.nombre,
            estado=llave.estado,
            tenedor=_tenedor(sesion, llave) if ve_tenedor else None,
        )
        for llave in _llaves_en_uso(sesion)
    ]


def _tenedor(sesion: Session, llave: Llave) -> Tenedor | None:
    if llave.estado == EstadoLlave.PRESTADA:
        prestamo = sesion.scalar(
            select(Prestamo).where(Prestamo.llave_id == llave.id, Prestamo.devuelto_en.is_(None))
        )
        if prestamo:
            return _datos_tenedor(prestamo.usuario, prestamo.retirado_en)
    if llave.estado == EstadoLlave.RESERVADA:
        reserva = sesion.scalar(
            select(Reserva).where(
                Reserva.llave_id == llave.id, Reserva.estado == EstadoReserva.PENDIENTE
            )
        )
        if reserva:
            return _datos_tenedor(reserva.usuario, reserva.creada_en)
    return None


def _datos_tenedor(usuario: Usuario, desde) -> Tenedor:
    return Tenedor(
        nombre=usuario.nombre, apellido=usuario.apellido, telefono=usuario.telefono, desde=desde
    )
