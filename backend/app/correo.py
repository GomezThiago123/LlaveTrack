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
