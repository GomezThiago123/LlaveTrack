"""Reglas de lo que pasa en el equipo: inicio, retiro (US-04/05) y devolucion (US-06).

No sabe nada de MQTT: recibe datos ya validados y devuelve los datos de la respuesta.
Si algo se rechaza, lanza RechazoEquipo con un motivo del protocolo (docs/protocolo-mqtt.md).
Como en app/servicios/reservas.py, no hace commit: lo hace quien la llama.
"""

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import config
from app.modelos import (
    Dispositivo,
    EstadoLlave,
    EstadoReserva,
    Llave,
    Prestamo,
    Reserva,
)
from app.servicios.reservas import vencer_reservas
from app.tipos import ahora_utc


class RechazoEquipo(Exception):
    """El servidor rechaza el evento. motivo: CODIGO_INVALIDO, CODIGO_VENCIDO, etc."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


def registrar_contacto(sesion: Session, device_id: str, online: bool | None = None) -> None:
    """Actualiza ultimo_contacto (y online, si se indica) de un equipo conocido."""
    valores: dict = {"ultimo_contacto": ahora_utc()}
    if online is not None:
        valores["online"] = online
    sesion.execute(update(Dispositivo).where(Dispositivo.device_id == device_id).values(**valores))


def inicio(sesion: Session, device_id: str, slots_totales: int, slots_reservados: list[int]) -> dict:
    """El equipo arranco: guarda su configuracion y le dice en que slot vacio quedarse."""
    dispositivo = sesion.scalar(select(Dispositivo).where(Dispositivo.device_id == device_id))
    if dispositivo is None:
        dispositivo = Dispositivo(device_id=device_id, slots_totales=slots_totales)
        sesion.add(dispositivo)
    dispositivo.slots_totales = slots_totales
    dispositivo.slots_reservados = slots_reservados
    dispositivo.online = True
    dispositivo.ultimo_contacto = ahora_utc()
    sesion.flush()
    # Despues del homing el disco esta en el slot 0: el vacio mas cercano es el que menos gira
    return {"slotReposo": _slot_vacio_mas_cercano(sesion, dispositivo, a=0)}


def solicitud_retiro(sesion: Session, codigo: str, ahora: datetime | None = None) -> dict:
    """El docente ingreso un codigo. Si es valido, dice que llave entregar y donde esta."""
    ahora = ahora or ahora_utc()
    vencer_reservas(sesion, ahora)

    reserva = _reserva_pendiente(sesion, codigo)
    if reserva is None:
        ultima = sesion.scalar(
            select(Reserva).where(Reserva.codigo == codigo).order_by(Reserva.id.desc())
        )
        vencida = ultima is not None and ultima.estado == EstadoReserva.VENCIDA
        raise RechazoEquipo("CODIGO_VENCIDO" if vencida else "CODIGO_INVALIDO")

    llave = reserva.llave
    if llave.slot is None:  # no deberia pasar: una llave reservada esta colgada en el disco
        raise RechazoEquipo("ERROR_INTERNO")

    # Que no venza mientras el disco gira y el docente retira la llave
    minimo = ahora + timedelta(seconds=config.retiro_margen_segundos)
    if reserva.expira_en < minimo:
        reserva.expira_en = minimo

    return {
        "slot": llave.slot,
        "uid": llave.rfid_uid,
        "aula": llave.aula.nombre,
        "apellido": reserva.usuario.apellido,
    }


def retiro_confirmado(sesion: Session, codigo: str, uid: str, slot: int) -> dict:
    """El docente se llevo la llave: la reserva se usa y empieza el prestamo.

    slot es donde estaba la llave realmente (puede no coincidir si el equipo tuvo que buscarla).
    Ese slot queda vacio y pasa a ser la posicion de reposo del disco.
    """
    reserva = _reserva_pendiente(sesion, codigo)
    if reserva is None or reserva.llave.rfid_uid != uid:
        raise RechazoEquipo("CODIGO_INVALIDO")

    # UPDATEs condicionales, igual que en las reservas: solo si nadie los cambio antes
    reserva_usada = sesion.execute(
        update(Reserva)
        .where(Reserva.id == reserva.id, Reserva.estado == EstadoReserva.PENDIENTE)
        .values(estado=EstadoReserva.USADA)
    ).rowcount
    llave_prestada = sesion.execute(
        update(Llave)
        .where(Llave.id == reserva.llave_id, Llave.estado == EstadoLlave.RESERVADA)
        .values(estado=EstadoLlave.PRESTADA, slot=None)
    ).rowcount
    if reserva_usada != 1 or llave_prestada != 1:
        raise RechazoEquipo("ERROR_INTERNO")

    sesion.add(
        Prestamo(
            llave_id=reserva.llave_id,
            usuario_id=reserva.usuario_id,
            reserva_id=reserva.id,
            retirado_en=ahora_utc(),
        )
    )
    return {}


def devolucion(sesion: Session, device_id: str, uid: str, slot: int) -> dict:
    """Se colgo una llave en el slot de la ventana: se cierra su prestamo."""
    llave = sesion.scalar(select(Llave).where(Llave.rfid_uid == uid))
    if llave is None:
        raise RechazoEquipo("LLAVE_DESCONOCIDA")

    prestamo = sesion.scalar(
        select(Prestamo).where(Prestamo.llave_id == llave.id, Prestamo.devuelto_en.is_(None))
    )
    if prestamo is None or llave.estado != EstadoLlave.PRESTADA:
        raise RechazoEquipo("SIN_PRESTAMO_ACTIVO")

    prestamo_cerrado = sesion.execute(
        update(Prestamo)
        .where(Prestamo.id == prestamo.id, Prestamo.devuelto_en.is_(None))
        .values(devuelto_en=ahora_utc())
    ).rowcount
    llave_disponible = sesion.execute(
        update(Llave)
        .where(Llave.id == llave.id, Llave.estado == EstadoLlave.PRESTADA)
        .values(estado=EstadoLlave.DISPONIBLE, slot=slot)
    ).rowcount
    if prestamo_cerrado != 1 or llave_disponible != 1:
        raise RechazoEquipo("ERROR_INTERNO")

    dispositivo = sesion.scalar(select(Dispositivo).where(Dispositivo.device_id == device_id))
    slot_reposo = _slot_vacio_mas_cercano(sesion, dispositivo, a=slot) if dispositivo else None
    return {
        "aula": llave.aula.nombre,
        "apellido": prestamo.usuario.apellido,  # quien la retiro
        "slotReposo": slot_reposo,
    }


def _reserva_pendiente(sesion: Session, codigo: str) -> Reserva | None:
    return sesion.scalar(
        select(Reserva).where(Reserva.codigo == codigo, Reserva.estado == EstadoReserva.PENDIENTE)
    )


def _slot_vacio_mas_cercano(sesion: Session, dispositivo: Dispositivo, a: int) -> int | None:
    """El slot sin llave mas cercano a la posicion `a` (contando que el disco es circular).

    Ocupados: los reservados del equipo (ej. el tag HOME) y los de las llaves colgadas.
    Devuelve None si el disco esta lleno.
    """
    total = dispositivo.slots_totales
    ocupados = set(dispositivo.slots_reservados)
    ocupados |= set(sesion.scalars(select(Llave.slot).where(Llave.slot.is_not(None))))
    vacios = [s for s in range(total) if s not in ocupados]
    if not vacios:
        return None

    def distancia(s: int) -> int:
        d = abs(s - a) % total
        return min(d, total - d)

    return min(vacios, key=lambda s: (distancia(s), s))
