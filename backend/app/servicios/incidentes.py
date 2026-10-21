"""Incidentes del equipo (US-05): cuando no puede entregar una llave, queda registrado
y el preceptor lo ve en la web. Abrirlos y resolverlos es US-21 (V2).

Como el resto de app/servicios, no hace commit: lo hace quien la llama.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modelos import Incidente, Reserva
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


def de_hoy(sesion: Session, ahora: datetime | None = None) -> list[Incidente]:
    """Los incidentes de hoy (dia de Argentina), del mas nuevo al mas viejo."""
    ahora = ahora or ahora_utc()
    medianoche = ahora.astimezone(ZONA_ARGENTINA).replace(hour=0, minute=0, second=0, microsecond=0)
    return list(
        sesion.scalars(
            select(Incidente)
            .options(joinedload(Incidente.aula), joinedload(Incidente.usuario))
            .where(Incidente.ocurrido_en >= medianoche)
            .order_by(Incidente.ocurrido_en.desc(), Incidente.id.desc())
        )
    )


def descripcion(tipo: str) -> str:
    """Texto para el preceptor: "LLAVE_NO_ENCONTRADA" -> "Llave no encontrada". Uno desconocido, legible."""
    return DESCRIPCIONES.get(tipo, tipo.replace("_", " ").capitalize())
