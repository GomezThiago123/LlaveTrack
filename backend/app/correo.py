"""Envio de mails con smtplib (libreria estandar de Python).

Sin SMTP_HOST en el .env no se manda nada: el mail se muestra en la consola del servidor.
Sirve para desarrollar y probar sin una cuenta de mail.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import config
from app.modelos import Usuario

log = logging.getLogger(__name__)


def enviar_correo(destino: str, asunto: str, cuerpo: str) -> None:
    if not config.smtp_host:
        log.warning("SMTP no configurado. Mail para %s:\n%s\n%s", destino, asunto, cuerpo)
        return

    mensaje = EmailMessage()
    mensaje["From"] = config.smtp_remitente or config.smtp_usuario
    mensaje["To"] = destino
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)

    with smtplib.SMTP(config.smtp_host, config.smtp_puerto, timeout=10) as smtp:
        smtp.starttls()  # cifra la conexion antes de mandar usuario y contrasena
        if config.smtp_usuario:
            smtp.login(config.smtp_usuario, config.smtp_clave or "")
        smtp.send_message(mensaje)


def enviar_link_recuperacion(usuario: Usuario, token: str) -> None:
    link = f"{config.web_url.rstrip('/')}/restablecer?token={token}"
    enviar_correo(
        usuario.email,
        "LlaveTrack: recuperar contraseña",
        f"Hola {usuario.nombre}:\n\n"
        f"Para elegir una contraseña nueva entrá a este link:\n{link}\n\n"
        f"El link vence en {config.recuperacion_minutos} minutos y sirve una sola vez.\n"
        "Si no lo pediste, ignorá este mail: tu contraseña no cambia.\n",
    )


def enviar_link_alta(usuario: Usuario, token: str) -> None:
    """US-09: el docente nuevo crea su contrasena con este link."""
    link = f"{config.web_url.rstrip('/')}/restablecer?token={token}"
    enviar_correo(
        usuario.email,
        "LlaveTrack: creá tu contraseña",
        f"Hola {usuario.nombre}:\n\n"
        "Te dieron de alta en LlaveTrack, el sistema para retirar las llaves de las aulas.\n"
        f"Para crear tu contraseña entrá a este link:\n{link}\n\n"
        f"El link vence en {config.alta_link_horas} horas y sirve una sola vez.\n",
    )


def enviar_recordatorio(usuario: Usuario, aula: str) -> None:
    """US-16: el preceptor le recuerda al docente que devuelva la llave."""
    enviar_correo(
        usuario.email,
        f"LlaveTrack: todavía tenés la llave del aula {aula}",
        f"Hola {usuario.nombre}:\n\n"
        f"Todavía tenés la llave del aula {aula}. Cuando termines, devolvela en el equipo:\n"
        "tecla B y colgala en el lugar vacío de la ventana.\n",
    )

