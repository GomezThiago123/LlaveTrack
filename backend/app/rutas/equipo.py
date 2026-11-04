"""Estado del equipo, tags RFID de las llaves (US-10) y llaves perdidas (US-11), para el preceptor."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.auth import preceptor_actual
from app.db import obtener_sesion
from app.errores import ErrorNegocio
from app.esquemas import BajaSalida, EquipoSalida, LlaveEquipo, PedidoBaja, PedidoRfid
from app.modelos import BajaLlave, Llave, Usuario
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
    llave = llaves.cambiar_rfid(sesion, llave_id, pedido.rfid_uid, pedido.slot)
    sesion.commit()
    return _llave(llave)


# --- US-11: llaves perdidas ---


def _baja(b: BajaLlave) -> BajaSalida:
    u = b.ultimo_usuario
    return BajaSalida(
        id=b.id,
        aula=b.aula.nombre,
        rfid_uid=b.rfid_uid,
        motivo=b.motivo,
        dada_en=b.dada_en,
        ultimo_docente=f"{u.nombre} {u.apellido}" if u else None,
        preceptor=f"{b.preceptor.nombre} {b.preceptor.apellido}",
    )


@router.post("/llaves/{llave_id}/baja", status_code=201)
def dar_de_baja(llave_id: int, pedido: PedidoBaja, sesion: SesionDep, preceptor: PreceptorDep) -> BajaSalida:
    """Solo preceptor y admin (US-11). La llave se perdio: deja de aparecer para retiro. Se repone
    con PUT /api/llaves/:id/rfid, indicando el tag nuevo y el lugar del disco."""
    baja = llaves.dar_de_baja(sesion, llave_id, pedido.motivo, preceptor)
    sesion.commit()
    return _baja(llaves.bajas(sesion, baja.aula_id)[0])


@router.get("/llaves/bajas")
def listar_bajas(
    sesion: SesionDep, _preceptor: PreceptorDep, aula_id: Annotated[int | None, Query(alias="aulaId")] = None
) -> list[BajaSalida]:
    """Solo preceptor y admin (US-11). Las bajas, de la mas nueva a la mas vieja."""
    lista = [_baja(b) for b in llaves.bajas(sesion, aula_id)]
    sesion.commit()  # guarda la renovacion de la sesion
    return lista
