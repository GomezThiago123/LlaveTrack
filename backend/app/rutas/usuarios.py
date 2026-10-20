"""Rutas para que el preceptor gestione cuentas (US-07: desbloquear antes de los 15 min)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth import preceptor_actual
from app.db import obtener_sesion
from app.esquemas import CuentaBloqueada
from app.modelos import Usuario
from app.servicios import auth

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
PreceptorDep = Annotated[Usuario, Depends(preceptor_actual)]


@router.get("/bloqueados")
def listar_bloqueados(sesion: SesionDep, _preceptor: PreceptorDep) -> list[CuentaBloqueada]:
    """Solo preceptor y admin. Cuentas bloqueadas por intentos fallidos."""
    lista = [CuentaBloqueada.model_validate(u) for u in auth.cuentas_bloqueadas(sesion)]
    sesion.commit()  # guarda la renovacion de la sesion
    return lista


@router.post("/{usuario_id}/desbloquear", status_code=204)
def desbloquear(usuario_id: int, sesion: SesionDep, _preceptor: PreceptorDep) -> Response:
    """Solo preceptor y admin. La cuenta puede volver a entrar enseguida."""
    auth.desbloquear(sesion, usuario_id)
    sesion.commit()
    return Response(status_code=204)
