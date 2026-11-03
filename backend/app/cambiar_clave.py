"""Cambia la contrasena de un usuario desde la terminal, sin mail (ej. antes de la demo).

Uso (desde backend/, con el .venv activado):
    python -m app.cambiar_clave ana.perez@example.com

Trabaja sobre la base del .env (DATABASE_URL): si apunta a Supabase, cambia la de Supabase.
Por eso muestra a que base va a escribir. La clave se pide por teclado y no se ve al escribirla.
"""

import getpass
import sys

from app.db import SesionLocal, engine
from app.errores import ErrorNegocio
from app.servicios.auth import CLAVE_MAX_BYTES, cambiar_clave

CLAVE_MIN = 8  # la misma que pide la web al elegir una contrasena nueva


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Uso: python -m app.cambiar_clave EMAIL")
    email = sys.argv[1]

    print(f"Base: {engine.url.render_as_string(hide_password=True)}")
    clave = getpass.getpass(f"Contraseña nueva para {email}: ")
    if len(clave) < CLAVE_MIN or len(clave.encode()) > CLAVE_MAX_BYTES:
        sys.exit(f"La contraseña tiene que tener entre {CLAVE_MIN} y {CLAVE_MAX_BYTES} caracteres.")
    if clave != getpass.getpass("Repetila: "):
        sys.exit("Las contraseñas no coinciden.")

    with SesionLocal() as sesion:
        try:
            cambiar_clave(sesion, email, clave)
        except ErrorNegocio as error:
            sys.exit(error.mensaje)
        sesion.commit()
    print("Listo. Las sesiones abiertas de ese usuario se cerraron.")


if __name__ == "__main__":
    main()
