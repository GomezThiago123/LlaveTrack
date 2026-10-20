"""Login con email y contrasena (US-01), bloqueo por intentos (US-07) y recuperacion (US-08).

Como el resto de app/servicios, no hace commit: lo hace la ruta que la llama.

Tokens: al navegador (cookie) o al mail (link) va un token al azar; en la base se guarda
solo su hash sha256. Si alguien copia la base, no puede usar esos tokens.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import config
from app.errores import ErrorNegocio
from app.modelos import RecuperacionClave, Sesion, Usuario
from app.tipos import ahora_utc

# bcrypt solo usa los primeros 72 bytes de la contrasena (y la version 5 rechaza las mas largas)
CLAVE_MAX_BYTES = 72


# --- Contrasenas y tokens ---


def hashear_clave(clave: str) -> str:
    return bcrypt.hashpw(clave.encode(), bcrypt.gensalt(config.bcrypt_rondas)).decode()


def verificar_clave(clave: str, hash_guardado: str | None) -> bool:
    datos = clave.encode()
    if hash_guardado is None or len(datos) > CLAVE_MAX_BYTES:
        return False
    return bcrypt.checkpw(datos, hash_guardado.encode())


# Se usa cuando el email no existe, para que la respuesta tarde lo mismo que con un
# email real (si no, midiendo el tiempo se podria saber que emails estan registrados)
_HASH_DE_RELLENO = hashear_clave("relleno")


def _nuevo_token() -> tuple[str, str]:
    """Devuelve (token, hash): el token va al navegador o al mail; el hash, a la base."""
    token = secrets.token_urlsafe(32)
    return token, _hash_token(token)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _buscar_usuario(sesion: Session, email: str) -> Usuario | None:
    return sesion.scalar(
        select(Usuario).where(Usuario.email == email.strip().lower(), Usuario.activo)
    )


# --- Login y sesion ---


def login(
    sesion: Session, email: str, clave: str, ahora: datetime | None = None
) -> tuple[Usuario, str]:
    """Verifica email y contrasena. Devuelve el usuario y el token de la sesion nueva.

    Si falla, lanza ErrorNegocio. OJO: aun asi hay que hacer commit, para que se guarde
    el intento fallido (si no, el bloqueo de US-07 nunca llegaria).
    """
    ahora = ahora or ahora_utc()
    usuario = _buscar_usuario(sesion, email)
    if usuario is None:
        verificar_clave(clave, _HASH_DE_RELLENO)
        raise _credenciales_invalidas()

    if usuario.bloqueado_hasta is not None and usuario.bloqueado_hasta > ahora:
        minutos = -(-(usuario.bloqueado_hasta - ahora) // timedelta(minutes=1))  # redondea para arriba
        raise ErrorNegocio(
            429,
            "CUENTA_BLOQUEADA",
            f"Demasiados intentos fallidos. Probá de nuevo en {minutos} min "
            "o recuperá tu contraseña.",
        )

    if not verificar_clave(clave, usuario.password_hash):
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= config.login_intentos_max:
            usuario.bloqueado_hasta = ahora + timedelta(minutes=config.login_bloqueo_minutos)
            usuario.intentos_fallidos = 0
        raise _credenciales_invalidas()

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    # De paso, borra las sesiones vencidas de este usuario para que la tabla no crezca
    sesion.execute(
        delete(Sesion).where(Sesion.usuario_id == usuario.id, Sesion.ultima_actividad < _limite(ahora))
    )
    token, token_hash = _nuevo_token()
    sesion.add(Sesion(token_hash=token_hash, usuario_id=usuario.id, creada_en=ahora, ultima_actividad=ahora))
    return usuario, token


def usuario_de_sesion(
    sesion: Session, token: str, ahora: datetime | None = None, renovar: bool = True
) -> Usuario | None:
    """El usuario dueno de la sesion, o None si no existe o vencio por inactividad.

    Cada uso renueva la sesion: vence tras SESION_SEGUNDOS *sin actividad* (US-01).
    renovar=False para los refrescos automaticos de la web: no son actividad del usuario.
    """
    ahora = ahora or ahora_utc()
    registro = sesion.scalar(select(Sesion).where(Sesion.token_hash == _hash_token(token)))
    if registro is None or registro.ultima_actividad < _limite(ahora) or not registro.usuario.activo:
        return None
    if renovar:
        registro.ultima_actividad = ahora
    return registro.usuario


def cerrar_sesion(sesion: Session, token: str) -> None:
    sesion.execute(delete(Sesion).where(Sesion.token_hash == _hash_token(token)))


def _limite(ahora: datetime) -> datetime:
    """Una sesion sin actividad desde antes de este momento esta vencida."""
    return ahora - timedelta(seconds=config.sesion_segundos)


def _credenciales_invalidas() -> ErrorNegocio:
    # Mismo mensaje si el email no existe o si la contrasena esta mal: no se revela cual fue
    return ErrorNegocio(401, "CREDENCIALES_INVALIDAS", "Email o contraseña incorrectos.")


# --- Desbloqueo manual por el preceptor (US-07) ---


def cuentas_bloqueadas(sesion: Session, ahora: datetime | None = None) -> list[Usuario]:
    """Usuarios con el login bloqueado por intentos fallidos, ordenados por apellido."""
    ahora = ahora or ahora_utc()
    return list(
        sesion.scalars(
            select(Usuario)
            .where(Usuario.bloqueado_hasta > ahora)
            .order_by(Usuario.apellido, Usuario.nombre)
        )
    )


def desbloquear(sesion: Session, usuario_id: int) -> None:
    """Levanta el bloqueo antes de los 15 min. Si la cuenta no estaba bloqueada, no cambia nada."""
    usuario = sesion.get(Usuario, usuario_id)
    if usuario is None:
        raise ErrorNegocio(404, "USUARIO_NO_ENCONTRADO", "El usuario no existe.")
    usuario.bloqueado_hasta = None
    usuario.intentos_fallidos = 0


# --- Recuperacion de contrasena ---


def pedir_recuperacion(
    sesion: Session, email: str, ahora: datetime | None = None
) -> tuple[Usuario, str] | None:
    """Crea un link de recuperacion. Devuelve (usuario, token) o None si el email no existe.

    La ruta responde lo mismo en los dos casos, para no revelar que emails estan cargados.
    """
    ahora = ahora or ahora_utc()
    usuario = _buscar_usuario(sesion, email)
    if usuario is None:
        return None
    token, token_hash = _nuevo_token()
    sesion.add(
        RecuperacionClave(
            token_hash=token_hash,
            usuario_id=usuario.id,
            creada_en=ahora,
            expira_en=ahora + timedelta(minutes=config.recuperacion_minutos),
        )
    )
    return usuario, token


def restablecer_clave(
    sesion: Session, token: str, clave_nueva: str, ahora: datetime | None = None
) -> None:
    """Cambia la contrasena con el token del link. El link sirve una sola vez."""
    ahora = ahora or ahora_utc()
    # UPDATE condicional: solo marca el link como usado si sigue sin usar y no vencio.
    # Si dos pedidos llegan con el mismo link, solo uno cambia la contrasena.
    recuperacion = sesion.scalar(
        select(RecuperacionClave).where(RecuperacionClave.token_hash == _hash_token(token))
    )
    usado = 0
    if recuperacion is not None:
        usado = sesion.execute(
            update(RecuperacionClave)
            .where(
                RecuperacionClave.id == recuperacion.id,
                RecuperacionClave.usada_en.is_(None),
                RecuperacionClave.expira_en > ahora,
            )
            .values(usada_en=ahora)
        ).rowcount
    if usado != 1 or not recuperacion.usuario.activo:
        raise ErrorNegocio(
            400, "LINK_INVALIDO", "El link no es válido o ya venció. Pedí uno nuevo."
        )

    usuario = recuperacion.usuario
    usuario.password_hash = hashear_clave(clave_nueva)
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    # Los otros links pendientes dejan de servir y se cierran las sesiones abiertas
    sesion.execute(
        update(RecuperacionClave)
        .where(RecuperacionClave.usuario_id == usuario.id, RecuperacionClave.usada_en.is_(None))
        .values(usada_en=ahora)
    )
    sesion.execute(delete(Sesion).where(Sesion.usuario_id == usuario.id))
