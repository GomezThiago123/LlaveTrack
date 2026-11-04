"""Incidentes del equipo (US-05 y US-21): cuando no puede entregar una llave, queda registrado
y el preceptor lo ve en la web. Mientras esta abierto, su aula figura "En revision" y no se
puede reservar; el preceptor lo marca resuelto y el aula vuelve a estar disponible.

Como el resto de app/servicios, no hace commit: lo hace quien la llama.
"""

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.errores import ErrorNegocio
from app.modelos import Incidente, Reserva, Usuario
from app.tipos import ZONA_ARGENTINA, ahora_utc

# Lo que ve el preceptor para cada error conocido (docs/protocolo-mqtt.md)
DESCRIPCIONES = {
    "LLAVE_NO_ENCONTRADA": "Llave no encontrada",
    "MOTOR_NO_GIRA": "Motor no gira",
}


def registrar(
    sesion: Session, device_id: str, tipo: str, codigo: str | None, detalle: str | None
) -> Incidente:
    """Guarda el error que mando el equipo. Con el codigo se sabe el aula y el docente."""
    reserva = None
    if codigo:
        # La mas reciente con ese codigo: los codigos se repiten con el tiempo (solo son
        # unicos entre las pendientes) y la reserva pudo vencer justo despues de la falla
        reserva = sesion.scalar(
            select(Reserva).where(Reserva.codigo == codigo).order_by(Reserva.creada_en.desc()).limit(1)
        )
    incidente = Incidente(
        device_id=device_id,
        tipo=tipo,
        detalle=detalle,
        aula_id=reserva.llave.aula_id if reserva else None,
        usuario_id=reserva.usuario_id if reserva else None,
    )
    sesion.add(incidente)
    return incidente


def abiertos_y_de_hoy(sesion: Session, ahora: datetime | None = None) -> list[Incidente]:
    """Los abiertos (de cualquier dia) y los resueltos hoy (dia de Argentina), del mas nuevo
    al mas viejo."""
    ahora = ahora or ahora_utc()
    medianoche = ahora.astimezone(ZONA_ARGENTINA).replace(hour=0, minute=0, second=0, microsecond=0)
    return list(
        sesion.scalars(
            select(Incidente)
            .options(
                joinedload(Incidente.aula), joinedload(Incidente.usuario), joinedload(Incidente.resuelto_por)
            )
            .where(or_(Incidente.resuelto_en.is_(None), Incidente.ocurrido_en >= medianoche))
            .order_by(Incidente.ocurrido_en.desc(), Incidente.id.desc())
        )
    )


def resolver(sesion: Session, incidente_id: int, preceptor: Usuario, ahora: datetime | None = None) -> Incidente:
    """US-21: el preceptor ya entrego la llave a mano y revisaron el equipo. Si ya estaba resuelto,
    no cambia nada (asi dos preceptores pueden apretar a la vez sin error)."""
    incidente = sesion.get(Incidente, incidente_id)
    if incidente is None:
        raise ErrorNegocio(404, "INCIDENTE_NO_ENCONTRADO", "El incidente no existe.")
    if incidente.resuelto_en is None:
        incidente.resuelto_en = ahora or ahora_utc()
        incidente.resuelto_por_id = preceptor.id
    return incidente


def aulas_en_revision(sesion: Session) -> set[int]:
    """Aulas con algun incidente abierto (US-21): no se pueden reservar."""
    return set(
        sesion.scalars(
            select(Incidente.aula_id).where(Incidente.resuelto_en.is_(None), Incidente.aula_id.is_not(None))
        )
    )


def descripcion(tipo: str) -> str:
    """Texto para el preceptor: "LLAVE_NO_ENCONTRADA" -> "Llave no encontrada". Uno desconocido, legible."""
    return DESCRIPCIONES.get(tipo, tipo.replace("_", " ").capitalize())
