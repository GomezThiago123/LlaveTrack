"""Estado del equipo y tags RFID de las llaves, para el preceptor (US-10)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import preceptor_actual
from app.db import obtener_sesion
from app.errores import ErrorNegocio
from app.esquemas import EquipoSalida, LlaveEquipo, PedidoRfid
from app.modelos import Llave, Usuario
from app.servicios import llaves

router = APIRouter(prefix="/api", tags=["equipo"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
PreceptorDep = Annotated[Usuario, Depends(preceptor_actual)]


def _llave(llave: Llave) -> LlaveEquipo:
    return LlaveEquipo(
        id=llave.id, aula=llave.aula.nombre, rfid_uid=llave.rfid_uid, slot=llave.slot, estado=llave.estado
    )


@router.get("/equipo")
def ver_equipo(sesion: SesionDep, _preceptor: PreceptorDep) -> EquipoSalida:
    """Solo preceptor y admin. Si está online, cuándo habló por última vez y qué hay en cada slot."""
    dispositivo, online, lista = llaves.estado_equipo(sesion)
    sesion.commit()  # guarda las reservas vencidas y la renovacion de la sesion
    return EquipoSalida(
        device_id=dispositivo.device_id if dispositivo else None,
        online=online,
        ultimo_contacto=dispositivo.ultimo_contacto if dispositivo else None,
        slots_totales=dispositivo.slots_totales if dispositivo else 0,
        slots_reservados=dispositivo.slots_reservados if dispositivo else [],
        llaves=[_llave(llave) for llave in lista],
    )


@router.post("/equipo/recalibrar", status_code=202)
def recalibrar(request: Request, sesion: SesionDep, _preceptor: PreceptorDep) -> None:
    """Solo preceptor y admin. El equipo repite el homing: sirve para sacarlo de un error
    del disco (ej. "Error del disco / Avisar porteria") sin tener que desenchufarlo."""
    dispositivo, online, _ = llaves.estado_equipo(sesion)
    sesion.commit()
    if dispositivo is None or not online:
        raise ErrorNegocio(409, "EQUIPO_DESCONECTADO", "El equipo no está conectado.")
    cliente = getattr(request.app.state, "cliente_mqtt", None)
    if cliente is None or not cliente.mandar_comando(dispositivo.device_id, "recalibrar"):
        raise ErrorNegocio(503, "SIN_BROKER", "El servidor no está conectado al broker MQTT.")


@router.put("/llaves/{llave_id}/rfid")
def cambiar_rfid(llave_id: int, pedido: PedidoRfid, sesion: SesionDep, _preceptor: PreceptorDep) -> LlaveEquipo:
    """Solo preceptor y admin (US-10). Asocia otro tag RFID a la llave de un aula."""
    llave = llaves.cambiar_rfid(sesion, llave_id, pedido.rfid_uid)
    sesion.commit()
    return _llave(llave)
