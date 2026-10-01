"""Rutas de reservas (US-03): pedir, consultar y cancelar la llave de un aula."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth import usuario_actual
from app.db import obtener_sesion
from app.esquemas import PedidoReserva, ReservaSalida
from app.modelos import Reserva, Usuario
from app.servicios import reservas

router = APIRouter(prefix="/api/reservas", tags=["reservas"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
UsuarioDep = Annotated[Usuario, Depends(usuario_actual)]


def _salida(reserva: Reserva) -> ReservaSalida:
    return ReservaSalida(
        id=reserva.id,
        aula=reserva.llave.aula.nombre,
        codigo=reserva.codigo,
        expira_en=reserva.expira_en,
        estado=reserva.estado,
    )


@router.post("", status_code=201)
def pedir_llave(pedido: PedidoReserva, sesion: SesionDep, usuario: UsuarioDep) -> ReservaSalida:
    """Reserva la llave del aula y devuelve el código para ingresar en el equipo."""
    reserva = reservas.crear_reserva(sesion, usuario, pedido.aula_id)
    sesion.commit()
    return _salida(reserva)


@router.get("/activa")
def ver_reserva_activa(sesion: SesionDep, usuario: UsuarioDep) -> ReservaSalida | None:
    """La reserva pendiente del usuario (para mostrar el código si recarga la página), o null."""
    reservas.vencer_reservas(sesion)
    sesion.commit()
    reserva = reservas.reserva_activa(sesion, usuario)
    return _salida(reserva) if reserva else None


@router.delete("/{reserva_id}", status_code=204)
def cancelar(reserva_id: int, sesion: SesionDep, usuario: UsuarioDep) -> Response:
    reservas.cancelar_reserva(sesion, usuario, reserva_id)
    sesion.commit()
    return Response(status_code=204)
