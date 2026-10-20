"""Rutas de login, logout y recuperacion de contrasena (US-01, US-07, US-08)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from app import correo
from app.auth import COOKIE_SESION, borrar_cookie, poner_cookie, usuario_actual
from app.db import obtener_sesion
from app.errores import ErrorNegocio
from app.esquemas import (
    Mensaje,
    PedidoLogin,
    PedidoRecuperacion,
    PedidoRestablecer,
    UsuarioSalida,
)
from app.modelos import Usuario
from app.servicios import auth

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]


@router.post("/login")
def login(pedido: PedidoLogin, sesion: SesionDep, respuesta: Response) -> UsuarioSalida:
    """Email y contraseña. Si son correctos, deja la sesión en una cookie httpOnly."""
    try:
        usuario, token = auth.login(sesion, pedido.email, pedido.clave)
    except ErrorNegocio:
        sesion.commit()  # guarda el intento fallido (o el bloqueo) antes de responder el error
        raise
    sesion.commit()
    poner_cookie(respuesta, token)
    return UsuarioSalida.model_validate(usuario)


@router.post("/logout", status_code=204)
def logout(
    sesion: SesionDep, token: Annotated[str | None, Cookie(alias=COOKIE_SESION)] = None
) -> Response:
    if token:
        auth.cerrar_sesion(sesion, token)
        sesion.commit()
    respuesta = Response(status_code=204)
    borrar_cookie(respuesta)
    return respuesta


@router.get("/yo")
def yo(sesion: SesionDep, usuario: Annotated[Usuario, Depends(usuario_actual)]) -> UsuarioSalida:
    """El usuario logueado. La web lo usa al abrir para saber si hay una sesión."""
    sesion.commit()  # guarda la renovacion de la sesion
    return UsuarioSalida.model_validate(usuario)


@router.post("/recuperar", status_code=202)
def recuperar(pedido: PedidoRecuperacion, sesion: SesionDep) -> Mensaje:
    """Manda un link para elegir una contraseña nueva. Responde lo mismo exista o no el email."""
    resultado = auth.pedir_recuperacion(sesion, pedido.email)
    sesion.commit()
    if resultado is not None:
        usuario, token = resultado
        try:
            correo.enviar_link_recuperacion(usuario, token)
        except Exception:
            # No se avisa a la web: revelaria que el email esta registrado
            log.exception("No se pudo mandar el mail de recuperacion a %s", usuario.email)
    return Mensaje(mensaje="Si el email está registrado, te enviamos un link.")


@router.post("/restablecer", status_code=204)
def restablecer(pedido: PedidoRestablecer, sesion: SesionDep) -> Response:
    """Cambia la contraseña con el token del link. Después hay que volver a ingresar."""
    auth.restablecer_clave(sesion, pedido.token, pedido.clave_nueva)
    sesion.commit()
    return Response(status_code=204)
