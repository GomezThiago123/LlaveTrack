"""Envio de mails, con la libreria estandar de Python.

- Con BREVO_API_KEY: por la API HTTPS de Brevo (en la nube: Render gratis bloquea SMTP).
- Con SMTP_HOST: por SMTP (por ejemplo, Gmail con una contrasena de aplicacion).
- Sin ninguno de los dos no se manda nada: el mail se muestra en la consola del servidor.
  Sirve para desarrollar y probar sin una cuenta de mail.
"""

import json
import logging
import smtplib
import urllib.request
from email.message import EmailMessage

from app.config import config
from app.modelos import Usuario

log = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _enviar_por_brevo(destino: str, asunto: str, cuerpo: str) -> None:
    datos = {
        "sender": {"name": "LlavesUBA", "email": config.brevo_remitente},
        "to": [{"email": destino}],
        "subject": asunto,
        "textContent": cuerpo,
    }
    pedido = urllib.request.Request(
        BREVO_URL,
        data=json.dumps(datos).encode(),
        headers={"api-key": config.brevo_api_key, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    # Si Brevo responde con un error, urlopen lanza una excepcion (igual que smtplib)
    with urllib.request.urlopen(pedido, timeout=10):
        pass


def enviar_correo(destino: str, asunto: str, cuerpo: str) -> None:
    if config.brevo_api_key:
        _enviar_por_brevo(destino, asunto, cuerpo)
        return
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
        "LlavesUBA: recuperar contraseña",
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
        "LlavesUBA: creá tu contraseña",
        f"Hola {usuario.nombre}:\n\n"
        "Te dieron de alta en LlavesUBA, el sistema para retirar las llaves de las aulas.\n"
        f"Para crear tu contraseña entrá a este link:\n{link}\n\n"
        f"El link vence en {config.alta_link_horas} horas y sirve una sola vez.\n",
    )


def enviar_devuelta_por_otro(titular: Usuario, aula: str, quien: Usuario, cuando) -> None:
    """US-20: otro docente devolvio la llave que tenia `titular`."""
    from app.tipos import ZONA_ARGENTINA

    hora = cuando.astimezone(ZONA_ARGENTINA).strftime("%H:%M")
    enviar_correo(
        titular.email,
        f"LlavesUBA: tu llave del aula {aula} fue devuelta",
        f"Hola {titular.nombre}:\n\n"
        f"Tu llave del aula {aula} fue devuelta por {quien.nombre} {quien.apellido} a las {hora}.\n"
        "Ya no figura a tu nombre.\n",
    )


def enviar_recordatorio(usuario: Usuario, aula: str) -> None:
    """US-16: el preceptor le recuerda al docente que devuelva la llave."""
    enviar_correo(
        usuario.email,
        f"LlavesUBA: todavía tenés la llave del aula {aula}",
        f"Hola {usuario.nombre}:\n\n"
        f"Todavía tenés la llave del aula {aula}. Cuando termines, devolvela en el equipo:\n"
        "tecla B y colgala en el lugar vacío de la ventana.\n",
    )

