"""Gestion de docentes por el preceptor (US-09): alta, listado y desactivar.

El docente nuevo no tiene contrasena: le llega un mail con un link para crearla.
Un usuario desactivado no puede iniciar sesion y se le cierran las sesiones abiertas.

Como el resto de app/servicios, no hace commit: lo hace quien la llama.
"""

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import config
from app.errores import ErrorNegocio
from app.modelos import Rol, Sesion, Usuario
from app.servicios.auth import crear_link_clave


def listar(sesion: Session) -> list[Usuario]:
    return list(sesion.scalars(select(Usuario).order_by(Usuario.apellido, Usuario.nombre)))


def dar_de_alta(
    sesion: Session, nombre: str, apellido: str, email: str, telefono: str | None, dni: str | None = None
) -> tuple[Usuario, str]:
    """Crea un docente y devuelve (usuario, token del link para que cree su contrasena)."""
    email = email.strip().lower()
    if sesion.scalar(select(Usuario).where(Usuario.email == email)) is not None:
        raise ErrorNegocio(409, "EMAIL_REPETIDO", "Ya hay un usuario cargado con ese email.")
    _validar_dni_libre(sesion, dni, None)
    usuario = Usuario(
        nombre=nombre.strip(),
        apellido=apellido.strip(),
        email=email,
        telefono=(telefono or "").strip() or None,
        rol=Rol.DOCENTE,
        password_hash=None,
        dni=dni or None,
    )
    sesion.add(usuario)
    sesion.flush()  # para tener el id antes de crear el link
    token = crear_link_clave(sesion, usuario, timedelta(hours=config.alta_link_horas))
    return usuario, token


def _validar_dni_libre(sesion: Session, dni: str | None, usuario_id: int | None) -> None:
    if not dni:
        return
    otro = sesion.scalar(select(Usuario).where(Usuario.dni == dni, Usuario.id != usuario_id))
    if otro is not None:
        raise ErrorNegocio(409, "DNI_REPETIDO", f"Ese DNI ya es de {otro.nombre} {otro.apellido}.")


def cambiar_dni(sesion: Session, usuario_id: int, dni: str | None) -> Usuario:
    """US-18: el DNI con el que se identifica en el equipo. Vacio = sin DNI."""
    usuario = sesion.get(Usuario, usuario_id)
    if usuario is None:
        raise ErrorNegocio(404, "USUARIO_NO_ENCONTRADO", "El usuario no existe.")
    _validar_dni_libre(sesion, dni, usuario.id)
    usuario.dni = dni or None
    return usuario


def cambiar_activo(sesion: Session, usuario_id: int, activo: bool, quien: Usuario) -> Usuario:
    usuario = sesion.get(Usuario, usuario_id)
    if usuario is None:
        raise ErrorNegocio(404, "USUARIO_NO_ENCONTRADO", "El usuario no existe.")
    if usuario.id == quien.id and not activo:
        raise ErrorNegocio(409, "NO_PUEDE_DESACTIVARSE", "No podés desactivar tu propia cuenta.")
    usuario.activo = activo
    if not activo:
        # Lo saca de la web enseguida, no recien cuando venza la sesion
        sesion.execute(delete(Sesion).where(Sesion.usuario_id == usuario.id))
    return usuario
