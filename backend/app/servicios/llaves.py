"""Las llaves del carrusel vistas por el preceptor: el estado del equipo, el tag RFID de cada
aula (US-10) y las llaves perdidas (US-11: se dan de baja y se reponen con un tag nuevo).

Como el resto de app/servicios, no hace commit: lo hace quien la llama.
"""

import re
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.errores import ErrorNegocio
from app.modelos import (
    Aula,
    BajaLlave,
    Dispositivo,
    EstadoLlave,
    EstadoReserva,
    Llave,
    Prestamo,
    Reserva,
    Usuario,
)
from app.servicios.conexion import equipo_online
from app.servicios.reservas import vencer_reservas
from app.tipos import ahora_utc


def estado_equipo(sesion: Session) -> tuple[Dispositivo | None, bool, list[Llave]]:
    """(equipo, si esta online, llaves ordenadas por slot). Incluye las de baja: el preceptor
    las repone desde ahi (US-11)."""
    vencer_reservas(sesion)
    dispositivo = sesion.scalars(select(Dispositivo).order_by(Dispositivo.id)).first()
    llaves = sesion.scalars(
        select(Llave)
        .join(Aula)
        .options(contains_eager(Llave.aula))  # el aula en la misma consulta (ver servicios/aulas.py)
        .order_by(Llave.slot, Aula.nombre)
    ).all()
    return dispositivo, equipo_online(sesion), list(llaves)


def cambiar_rfid(sesion: Session, llave_id: int, uid: str, slot: int | None = None) -> Llave:
    """Asocia otro tag a la llave (US-10). Un tag no puede pertenecer a dos aulas.

    Con `slot`, ademas dice en que lugar del disco quedo colgada. Para reponer una llave dada de
    baja (US-11) el slot es obligatorio: vuelve a estar DISPONIBLE y el equipo tiene que saber
    donde buscarla.
    """
    uid = re.sub(r"[\s:-]", "", uid).upper()  # "04:a1:b2:c3" -> "04A1B2C3", como en el protocolo
    if not re.fullmatch(r"[0-9A-F]{8,20}", uid):
        raise ErrorNegocio(422, "UID_INVALIDO", "El UID tiene que ser hexadecimal (ej. 04A1B2C3).")
    llave = sesion.get(Llave, llave_id)
    if llave is None:
        raise ErrorNegocio(404, "LLAVE_NO_ENCONTRADA", "La llave no existe.")
    otra = sesion.scalar(select(Llave).where(Llave.rfid_uid == uid, Llave.id != llave_id))
    if otra is not None:
        raise ErrorNegocio(409, "TAG_REPETIDO", f"Este tag ya pertenece al aula {otra.aula.nombre}.")
    if llave.estado == EstadoLlave.BAJA and slot is None:
        raise ErrorNegocio(422, "SLOT_REQUERIDO", "Indicá en qué lugar del disco colgaste la llave nueva.")
    if slot is not None:
        if llave.estado == EstadoLlave.PRESTADA:
            raise ErrorNegocio(409, "LLAVE_PRESTADA", "La llave está prestada: no está en el disco.")
        _validar_slot_libre(sesion, slot, llave.id)
        llave.slot = slot
    if llave.estado == EstadoLlave.BAJA:
        llave.estado = EstadoLlave.DISPONIBLE  # US-11: repuesta
    llave.rfid_uid = uid
    return llave


def _validar_slot_libre(sesion: Session, slot: int, llave_id: int) -> None:
    dispositivo = sesion.scalars(select(Dispositivo).order_by(Dispositivo.id)).first()
    if dispositivo and not 0 <= slot < dispositivo.slots_totales:
        raise ErrorNegocio(422, "SLOT_INVALIDO", f"El disco tiene los lugares 0 a {dispositivo.slots_totales - 1}.")
    if dispositivo and slot in dispositivo.slots_reservados:
        raise ErrorNegocio(409, "SLOT_OCUPADO", f"El lugar {slot} es del tag HOME: no lleva llave.")
    otra = sesion.scalar(select(Llave).where(Llave.slot == slot, Llave.id != llave_id))
    if otra is not None:
        raise ErrorNegocio(409, "SLOT_OCUPADO", f"En el lugar {slot} está la llave del aula {otra.aula.nombre}.")


def dar_de_baja(
    sesion: Session, llave_id: int, motivo: str, preceptor: Usuario, ahora: datetime | None = None
) -> BajaLlave:
    """US-11: la llave se perdio. Deja de aparecer para retiro y queda la constancia.

    Si estaba prestada, el prestamo se cierra como perdido (no "devuelto"); si estaba reservada,
    la reserva se cancela.
    """
    ahora = ahora or ahora_utc()
    vencer_reservas(sesion, ahora)
    llave = sesion.get(Llave, llave_id)
    if llave is None:
        raise ErrorNegocio(404, "LLAVE_NO_ENCONTRADA", "La llave no existe.")
    if llave.estado == EstadoLlave.BAJA:
        raise ErrorNegocio(409, "YA_DADA_DE_BAJA", f"La llave del aula {llave.aula.nombre} ya está dada de baja.")

    activo = sesion.scalar(select(Prestamo).where(Prestamo.llave_id == llave.id, Prestamo.devuelto_en.is_(None)))
    if activo is not None:
        activo.devuelto_en = ahora
        activo.perdida = True
        ultimo_usuario_id = activo.usuario_id
    else:
        ultimo_usuario_id = sesion.scalar(
            select(Prestamo.usuario_id)
            .where(Prestamo.llave_id == llave.id)
            .order_by(Prestamo.retirado_en.desc())
            .limit(1)
        )
    sesion.execute(
        update(Reserva)
        .where(Reserva.llave_id == llave.id, Reserva.estado == EstadoReserva.PENDIENTE)
        .values(estado=EstadoReserva.CANCELADA)
    )
    baja = BajaLlave(
        llave_id=llave.id,
        aula_id=llave.aula_id,
        rfid_uid=llave.rfid_uid,
        motivo=motivo.strip(),
        dada_en=ahora,
        ultimo_usuario_id=ultimo_usuario_id,
        preceptor_id=preceptor.id,
    )
    llave.estado = EstadoLlave.BAJA
    llave.slot = None
    sesion.add(baja)
    sesion.flush()
    return baja


def bajas(sesion: Session, aula_id: int | None = None) -> list[BajaLlave]:
    """US-11: las bajas, de la mas nueva a la mas vieja (todas, o las de un aula)."""
    consulta = (
        select(BajaLlave)
        .options(joinedload(BajaLlave.aula), joinedload(BajaLlave.ultimo_usuario), joinedload(BajaLlave.preceptor))
        .order_by(BajaLlave.dada_en.desc(), BajaLlave.id.desc())
    )
    if aula_id is not None:
        consulta = consulta.where(BajaLlave.aula_id == aula_id)
    return list(sesion.scalars(consulta))
