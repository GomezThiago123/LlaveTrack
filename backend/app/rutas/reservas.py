"""Rutas de reservas (US-03): pedir, consultar y cancelar la llave de un aula."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import usuario_actual
from app.db import obtener_sesion
from app.errores import ErrorNegocio
from app.esquemas import PedidoReserva, ReservaSalida
from app.modelos import Dispositivo, Reserva, Usuario
from app.servicios import reservas

router = APIRouter(prefix="/api/reservas", tags=["reservas"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
UsuarioDep = Annotated[Usuario, Depends(usuario_actual)]


def _salida(reserva: Reserva) -> ReservaSalida:
    return ReservaSalida(
        id=reserva.id,
        aula=reserva.llave.aula.nombre,
        codigo=reserva.codigo,
        creada_en=reserva.creada_en,
        expira_en=reserva.expira_en,
        estado=reserva.estado,
        hora_fin=reserva.hora_fin,
    )


@router.post("", status_code=201)
def pedir_llave(
    pedido: PedidoReserva, request: Request, sesion: SesionDep, usuario: UsuarioDep
) -> ReservaSalida:
    """Reserva la llave del aula y le pide al equipo que la entregue enseguida (entrega directa,
    05/11/2026: el docente la pide parado frente al equipo, sin escribir ningun codigo).

    El codigo de la reserva queda interno: viaja en el comando `entregar` y el equipo lo usa como
    si se lo hubieran escrito. Si el comando no sale, la reserva se cancela.
    """
    reserva = reservas.crear_reserva(sesion, usuario, pedido.aula_id, hora_fin=pedido.hora_fin)
    sesion.commit()
    dispositivo = sesion.scalars(select(Dispositivo).order_by(Dispositivo.id)).first()
    cliente = getattr(request.app.state, "cliente_mqtt", None)
    enviado = (
        dispositivo is not None
        and cliente is not None
        and cliente.mandar_comando(dispositivo.device_id, "entregar", codigo=reserva.codigo)
    )
    if not enviado:
        reservas.cancelar_reserva(sesion, usuario, reserva.id)
        sesion.commit()
        raise ErrorNegocio(503, "SIN_BROKER", "No se pudo avisar al equipo. Probá de nuevo en unos segundos.")
    return _salida(reserva)


@router.get("/activa")
def ver_reserva_activa(sesion: SesionDep, usuario: UsuarioDep) -> ReservaSalida | None:
    """La reserva pendiente del usuario (para mostrar el código si recarga la página), o null."""
    reservas.vencer_reservas(sesion)
    sesion.commit()
    reserva = reservas.reserva_activa(sesion, usuario)
    return _salida(reserva) if reserva else None


@router.get("/{reserva_id}")
def ver_reserva(reserva_id: int, sesion: SesionDep, usuario: UsuarioDep) -> ReservaSalida:
    """Una reserva propia en cualquier estado: la web la consulta para saber si ya se retiró la llave."""
    reserva = reservas.reserva_del_usuario(sesion, usuario, reserva_id)
    sesion.commit()
    return _salida(reserva)


@router.delete("/{reserva_id}", status_code=204)
def cancelar(reserva_id: int, sesion: SesionDep, usuario: UsuarioDep) -> Response:
    reservas.cancelar_reserva(sesion, usuario, reserva_id)
    sesion.commit()
    return Response(status_code=204)
