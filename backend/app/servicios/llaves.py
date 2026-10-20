"""Las llaves del carrusel vistas por el preceptor: el estado del equipo y el tag RFID de
cada aula (US-10).

US-10 pide un "modo alta" en el equipo (acercar el tag y ver el UID leido). Hasta que el
firmware lo tenga, el UID se escribe a mano: lo muestra el modo diagnostico del equipo.

Como el resto de app/servicios, no hace commit: lo hace quien la llama.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errores import ErrorNegocio
from app.modelos import Aula, Dispositivo, EstadoLlave, Llave
from app.servicios.conexion import equipo_online
from app.servicios.reservas import vencer_reservas


def estado_equipo(sesion: Session) -> tuple[Dispositivo | None, bool, list[Llave]]:
    """(equipo, si esta online, llaves que no estan de baja ordenadas por slot)."""
    vencer_reservas(sesion)
    dispositivo = sesion.scalars(select(Dispositivo).order_by(Dispositivo.id)).first()
    llaves = sesion.scalars(
        select(Llave).join(Aula).where(Llave.estado != EstadoLlave.BAJA).order_by(Llave.slot, Aula.nombre)
    ).all()
    return dispositivo, equipo_online(sesion), list(llaves)


def cambiar_rfid(sesion: Session, llave_id: int, uid: str) -> Llave:
    """Asocia otro tag a la llave. Un tag no puede pertenecer a dos aulas."""
    uid = re.sub(r"[\s:-]", "", uid).upper()  # "04:a1:b2:c3" -> "04A1B2C3", como en el protocolo
    if not re.fullmatch(r"[0-9A-F]{8,20}", uid):
        raise ErrorNegocio(422, "UID_INVALIDO", "El UID tiene que ser hexadecimal (ej. 04A1B2C3).")
    llave = sesion.get(Llave, llave_id)
    if llave is None:
        raise ErrorNegocio(404, "LLAVE_NO_ENCONTRADA", "La llave no existe.")
    otra = sesion.scalar(select(Llave).where(Llave.rfid_uid == uid, Llave.id != llave_id))
    if otra is not None:
        raise ErrorNegocio(409, "TAG_REPETIDO", f"Este tag ya pertenece al aula {otra.aula.nombre}.")
    llave.rfid_uid = uid
    return llave
