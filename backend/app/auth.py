"""Identifica al usuario que hace cada pedido.

TEMPORAL (Fase 1): en modo desarrollo el usuario se indica con el encabezado
X-Usuario-Email. En la Fase 2 se reemplaza por la sesion del login.
"""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import config
from app.db import obtener_sesion
from app.errores import ErrorNegocio
from app.modelos import Usuario


def usuario_actual(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    x_usuario_email: Annotated[
        str | None, Header(description="TEMPORAL: email del usuario (solo en modo desarrollo)")
    ] = None,
) -> Usuario:
    if not config.modo_desarrollo or not x_usuario_email:
        raise ErrorNegocio(401, "NO_AUTENTICADO", "Tenés que iniciar sesión.")
    usuario = sesion.scalar(
        select(Usuario).where(Usuario.email == x_usuario_email.strip().lower(), Usuario.activo)
    )
    if usuario is None:
        raise ErrorNegocio(401, "NO_AUTENTICADO", "Usuario inexistente o inactivo.")
    return usuario
