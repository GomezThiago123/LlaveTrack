"""Rutas de prestamos: los mios (US-17), el historial del preceptor (US-12 y US-13) y el
recordatorio de devolucion (US-16)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import correo
from app.auth import preceptor_actual, usuario_actual
from app.db import obtener_sesion
from app.esquemas import FiltrosHistorial, HistorialSalida, PersonaSalida, PrestamoSalida
from app.modelos import Prestamo, Usuario
from app.servicios import prestamos

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prestamos", tags=["prestamos"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
PreceptorDep = Annotated[Usuario, Depends(preceptor_actual)]


def _salida(p: Prestamo) -> PrestamoSalida:
    u = p.usuario
    return PrestamoSalida(
        id=p.id,
        aula=p.llave.aula.nombre,
        docente=PersonaSalida(id=u.id, nombre=u.nombre, apellido=u.apellido, email=u.email, telefono=u.telefono),
        retirado_en=p.retirado_en,
        devuelto_en=p.devuelto_en,
        recordatorio_enviado_en=p.recordatorio_enviado_en,
    )


@router.get("/mios")
def mis_prestamos(
    sesion: SesionDep, usuario: Annotated[Usuario, Depends(usuario_actual)]
) -> list[PrestamoSalida]:
    """Con login (US-17). Primero las llaves que tengo, después mis préstamos anteriores."""
    lista = [_salida(p) for p in prestamos.mis_prestamos(sesion, usuario)]
    sesion.commit()  # guarda la renovacion de la sesion
    return lista


@router.get("")
def historial(
    sesion: SesionDep, _preceptor: PreceptorDep, filtros: Annotated[FiltrosHistorial, Query()]
) -> HistorialSalida:
    """Solo preceptor y admin (US-12 y US-13). Fechas en días de Argentina (desde y hasta incluidos)."""
    lista = prestamos.historial(
        sesion, filtros.aula_id, filtros.usuario_id, filtros.desde, filtros.hasta, filtros.estado
    )
    en_poder = prestamos.llaves_en_poder(sesion, filtros.usuario_id) if filtros.usuario_id else None
    sesion.commit()
    return HistorialSalida(prestamos=[_salida(p) for p in lista], en_poder=en_poder)


@router.post("/{prestamo_id}/recordatorio")
def enviar_recordatorio(prestamo_id: int, sesion: SesionDep, _preceptor: PreceptorDep) -> PrestamoSalida:
    """Solo preceptor y admin (US-16). Le manda un mail al docente para que devuelva la llave."""
    prestamo = prestamos.marcar_recordatorio(sesion, prestamo_id)
    sesion.commit()
    try:
        correo.enviar_recordatorio(prestamo.usuario, prestamo.llave.aula.nombre)
    except Exception:
        log.exception("No se pudo mandar el recordatorio del prestamo %s", prestamo_id)
    return _salida(prestamo)
