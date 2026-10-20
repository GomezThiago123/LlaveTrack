"""Incidentes del equipo para el preceptor (US-05)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import preceptor_actual
from app.db import obtener_sesion
from app.esquemas import IncidenteSalida
from app.modelos import Usuario
from app.servicios import incidentes

router = APIRouter(prefix="/api/incidentes", tags=["incidentes"])


@router.get("")
def listar_de_hoy(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    _preceptor: Annotated[Usuario, Depends(preceptor_actual)],
) -> list[IncidenteSalida]:
    """Solo preceptor y admin. Las fallas del equipo de hoy, de la mas nueva a la mas vieja."""
    lista = [
        IncidenteSalida(
            id=i.id,
            ocurrido_en=i.ocurrido_en,
            tipo=i.tipo,
            descripcion=incidentes.descripcion(i.tipo),
            aula=i.aula.nombre if i.aula else None,
            docente=f"{i.usuario.nombre} {i.usuario.apellido}" if i.usuario else None,
            detalle=i.detalle,
        )
        for i in incidentes.de_hoy(sesion)
    ]
    sesion.commit()  # guarda la renovacion de la sesion
    return lista
