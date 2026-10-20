"""Rutas de consulta de aulas (US-02)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import usuario_actual
from app.db import obtener_sesion
from app.esquemas import AulaDetalle, EstadoPublico
from app.modelos import Usuario
from app.servicios import aulas

router = APIRouter(prefix="/api", tags=["aulas"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]


@router.get("/publico/estado")
def estado_publico(sesion: SesionDep) -> EstadoPublico:
    """Sin login: disponibilidad de cada aula y si el equipo está online. Sin datos personales."""
    estado = aulas.estado_publico(sesion)
    sesion.commit()  # guarda las reservas que se hayan vencido
    return estado


@router.get("/aulas")
def listar_aulas(
    sesion: SesionDep, _usuario: Annotated[Usuario, Depends(usuario_actual)]
) -> list[AulaDetalle]:
    """Con login. Además del estado, quién tiene cada llave, desde qué hora y su teléfono."""
    lista = aulas.aulas_con_tenedor(sesion)
    sesion.commit()
    return lista
