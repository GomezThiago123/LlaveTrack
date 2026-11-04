"""Tareas en segundo plano del servidor. Hoy, una sola: los avisos automaticos de US-16.

Corre en su propio hilo (como paho-mqtt) y abre una sesion de base corta en cada vuelta.
"""

import logging
import threading

from app import correo
from app.config import config
from app.db import SesionLocal
from app.servicios import recordatorios
from app.tipos import ahora_utc

log = logging.getLogger(__name__)


def revisar_recordatorios(fabrica_sesiones=SesionLocal) -> int:
    """Una vuelta: manda los avisos que correspondan. Devuelve cuantos mando."""
    with fabrica_sesiones() as sesion:
        pendientes = recordatorios.avisos_pendientes(sesion, ahora_utc())
        datos = [(p.usuario, p.llave.aula.nombre) for p in pendientes]
        sesion.commit()
    for usuario, aula in datos:
        try:
            correo.enviar_recordatorio(usuario, aula)
            log.info("Aviso automatico a %s por la llave del aula %s", usuario.email, aula)
        except Exception:
            log.exception("No se pudo mandar el aviso automatico a %s", usuario.email)
    return len(datos)


class TareaRecordatorios(threading.Thread):
    def __init__(self):
        super().__init__(name="recordatorios", daemon=True)
        self.frenar = threading.Event()

    def run(self) -> None:
        while not self.frenar.wait(config.recordatorios_cada_segundos):
            try:
                revisar_recordatorios()
            except Exception:  # un error de base no tiene que matar el hilo
                log.exception("Fallo la revision de recordatorios")

    def detener(self) -> None:
        self.frenar.set()
