"""Incidentes del equipo para el preceptor (US-05 y US-21)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth import preceptor_actual
from app.db import obtener_sesion
from app.esquemas import IncidenteSalida
from app.modelos import Incidente, Usuario
from app.servicios import incidentes
from app.servicios.conexion import equipo_online

router = APIRouter(prefix="/api/incidentes", tags=["incidentes"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
PreceptorDep = Annotated[Usuario, Depends(preceptor_actual)]


def _salida(i: Incidente) -> IncidenteSalida:
    return IncidenteSalida(
        id=i.id,
        ocurrido_en=i.ocurrido_en,
        tipo=i.tipo,
        descripcion=incidentes.descripcion(i.tipo),
        aula=i.aula.nombre if i.aula else None,
        docente=f"{i.usuario.nombre} {i.usuario.apellido}" if i.usuario else None,
        detalle=i.detalle,
        resuelto_en=i.resuelto_en,
        resuelto_por=f"{i.resuelto_por.nombre} {i.resuelto_por.apellido}" if i.resuelto_por else None,
    )


@router.get("")
def listar(sesion: SesionDep, _preceptor: PreceptorDep) -> list[IncidenteSalida]:
    """Solo preceptor y admin. Los abiertos (de cualquier dia) y los resueltos hoy, del mas nuevo
    al mas viejo. Mientras un incidente esta abierto, su aula figura "En revision" (US-21)."""
    lista = [_salida(i) for i in incidentes.abiertos_y_de_hoy(sesion)]
    sesion.commit()  # guarda la renovacion de la sesion
    return lista


@router.post("/{incidente_id}/resolver")
def resolver(incidente_id: int, request: Request, sesion: SesionDep, preceptor: PreceptorDep) -> IncidenteSalida:
    """Solo preceptor y admin (US-21). El aula vuelve a estar disponible para reservar.

    Si era una falla del motor o del lector y el equipo sigue trabado, ademas le pide que
    recalibre: "resuelto" quiere decir que ya lo revisaron. Si el homing anda, el equipo manda
    `inicio` y vuelve a entregar llaves; si no, manda otro error y queda un incidente nuevo.
    """
    incidente = incidentes.resolver(sesion, incidente_id, preceptor)
    recalibrar = (
        incidente.tipo in incidentes.FALLAS_DEL_EQUIPO
        and incidentes.equipo_con_falla(sesion)
        and equipo_online(sesion)
    )
    sesion.commit()
    sesion.refresh(incidente)
    salida = _salida(incidente)
    if recalibrar:
        # Sin broker no sale: el incidente igual queda resuelto y se puede recalibrar desde Equipo
        cliente = getattr(request.app.state, "cliente_mqtt", None)
        salida.recalibrando = cliente is not None and cliente.mandar_comando(incidente.device_id, "recalibrar")
    return salida
