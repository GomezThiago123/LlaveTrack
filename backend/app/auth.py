"""Identifica al usuario que hace cada pedido, a partir de la cookie de sesion.

La cookie es httpOnly (el JavaScript de la web no la puede leer, asi un script malicioso
no puede robarla) y SameSite=Lax (otro sitio no puede hacer pedidos con ella).
"""

from typing import Annotated

from fastapi import Cookie, Depends, Header, Response
from sqlalchemy.orm import Session

from app.config import config
from app.db import obtener_sesion
from app.errores import ErrorNegocio
from app.modelos import Rol, Usuario
from app.servicios import auth

COOKIE_SESION = "llavetrack_sesion"


def usuario_actual(
    sesion: Annotated[Session, Depends(obtener_sesion)],
    token: Annotated[str | None, Cookie(alias=COOKIE_SESION)] = None,
    refresco_automatico: Annotated[
        str | None,
        Header(
            alias="X-Refresco-Automatico",
            description="La web lo manda en los pedidos que hace sola cada 5 s: no renuevan la sesión",
        ),
    ] = None,
) -> Usuario:
    """Dependencia de FastAPI para las rutas que necesitan login.

    Renueva la sesion; la ruta hace el commit (asi se guarda la ultima actividad).
    Los refrescos automaticos no la renuevan: si no, con la web abierta nunca venceria.
    """
    if not token:
        raise ErrorNegocio(401, "NO_AUTENTICADO", "Tenés que iniciar sesión.")
    usuario = auth.usuario_de_sesion(sesion, token, renovar=refresco_automatico is None)
    if usuario is None:
        raise ErrorNegocio(401, "SESION_VENCIDA", "Tu sesión venció. Volvé a ingresar.")
    return usuario


def preceptor_actual(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> Usuario:
    """Como usuario_actual, pero solo deja pasar a preceptores y administradores."""
    if usuario.rol not in (Rol.PRECEPTOR, Rol.ADMIN):
        raise ErrorNegocio(403, "SIN_PERMISO", "Solo el preceptor puede hacer esto.")
    return usuario


def poner_cookie(respuesta: Response, token: str) -> None:
    # Sin max_age: el navegador la borra al cerrarse. El vencimiento por inactividad lo controla el servidor
    respuesta.set_cookie(
        COOKIE_SESION,
        token,
        httponly=True,
        samesite="lax",
        secure=config.cookie_segura,
        path="/",
    )


def borrar_cookie(respuesta: Response) -> None:
    respuesta.delete_cookie(
        COOKIE_SESION, httponly=True, samesite="lax", secure=config.cookie_segura, path="/"
    )
