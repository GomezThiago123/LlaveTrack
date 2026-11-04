"""Rutas para que el preceptor gestione cuentas: desbloquear (US-07) y dar de alta,
listar y desactivar docentes (US-09)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import correo
from app.auth import preceptor_actual
from app.db import obtener_sesion
from app.errores import ErrorNegocio
from app.esquemas import CuentaBloqueada, PedidoActivo, PedidoAlta, UsuarioDetalle
from app.modelos import Usuario
from app.servicios import auth, usuarios

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])

SesionDep = Annotated[Session, Depends(obtener_sesion)]
PreceptorDep = Annotated[Usuario, Depends(preceptor_actual)]


def _detalle(u: Usuario) -> UsuarioDetalle:
    return UsuarioDetalle(
        id=u.id,
        nombre=u.nombre,
        apellido=u.apellido,
        email=u.email,
        telefono=u.telefono,
        rol=u.rol,
        activo=u.activo,
        tiene_clave=u.password_hash is not None,
        dni=u.dni,
    )


@router.get("")
def listar(sesion: SesionDep, _preceptor: PreceptorDep) -> list[UsuarioDetalle]:
    """Solo preceptor y admin (US-09). Todos los usuarios, por apellido."""
    lista = [_detalle(u) for u in usuarios.listar(sesion)]
    sesion.commit()  # guarda la renovacion de la sesion
    return lista


@router.post("", status_code=201)
def dar_de_alta(pedido: PedidoAlta, sesion: SesionDep, _preceptor: PreceptorDep) -> UsuarioDetalle:
    """Solo preceptor y admin (US-09). Crea un docente y le manda un mail para crear su contraseña."""
    usuario, token = usuarios.dar_de_alta(
        sesion, pedido.nombre, pedido.apellido, pedido.email, pedido.telefono, pedido.dni
    )
    sesion.commit()
    try:
        correo.enviar_link_alta(usuario, token)
    except Exception:
        # El docente queda cargado: puede usar "Olvidé mi contraseña" para recibir otro link
        log.exception("No se pudo mandar el mail de alta a %s", usuario.email)
    return _detalle(usuario)


@router.patch("/{usuario_id}")
def cambiar_activo(
    usuario_id: int, pedido: PedidoActivo, sesion: SesionDep, preceptor: PreceptorDep
) -> UsuarioDetalle:
    """Solo preceptor y admin. Activar o desactivar (US-09: desactivado no puede iniciar sesión
    ni usar su DNI en el equipo) y/o cargar el DNI (US-18)."""
    usuario = None
    if "dni" in pedido.model_fields_set:
        usuario = usuarios.cambiar_dni(sesion, usuario_id, pedido.dni)
    if pedido.activo is not None:
        usuario = usuarios.cambiar_activo(sesion, usuario_id, pedido.activo, quien=preceptor)
    if usuario is None:
        raise ErrorNegocio(422, "DATOS_INVALIDOS", "No hay nada para cambiar.")
    sesion.commit()
    return _detalle(usuario)


@router.get("/bloqueados")
def listar_bloqueados(sesion: SesionDep, _preceptor: PreceptorDep) -> list[CuentaBloqueada]:
    """Solo preceptor y admin (US-07). Cuentas bloqueadas por intentos fallidos."""
    lista = [CuentaBloqueada.model_validate(u) for u in auth.cuentas_bloqueadas(sesion)]
    sesion.commit()  # guarda la renovacion de la sesion
    return lista


@router.post("/{usuario_id}/desbloquear", status_code=204)
def desbloquear(usuario_id: int, sesion: SesionDep, _preceptor: PreceptorDep) -> Response:
    """Solo preceptor y admin (US-07). La cuenta puede volver a entrar enseguida."""
    auth.desbloquear(sesion, usuario_id)
    sesion.commit()
    return Response(status_code=204)
