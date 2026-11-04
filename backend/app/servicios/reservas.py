"""Reglas de las reservas (US-03).

Estas funciones no hacen commit: lo hace quien las llama (la ruta HTTP o el cliente MQTT),
asi todos los cambios de un pedido se guardan juntos o no se guarda ninguno.

Regla principal: una llave nunca puede quedar tomada dos veces. Cada cambio de estado
es un UPDATE condicional ("cambiala a RESERVADA solo si sigue DISPONIBLE") y se
verifica cuantas filas cambio. Si cambio 0, otro pedido gano.
"""

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import config
from app.errores import ErrorNegocio
from app.modelos import Aula, EstadoLlave, EstadoReserva, Llave, Reserva, Usuario
from app.servicios.conexion import equipo_online
from app.servicios.incidentes import aulas_en_revision
from app.tipos import ZONA_ARGENTINA, ahora_utc


def vencer_reservas(sesion: Session, ahora: datetime | None = None) -> int:
    """Pasa a VENCIDA las reservas pendientes que ya expiraron y libera sus llaves.

    Se llama antes de cada consulta o cambio, asi nunca se ve una reserva vieja como vigente.
    Devuelve cuantas reservas vencio.
    """
    ahora = ahora or ahora_utc()
    vencidas = sesion.scalars(
        select(Reserva).where(Reserva.estado == EstadoReserva.PENDIENTE, Reserva.expira_en <= ahora)
    ).all()
    for reserva in vencidas:
        _cerrar_reserva(sesion, reserva, EstadoReserva.VENCIDA)
    return len(vencidas)


def hora_fin_desde_texto(hora_fin: str, ahora: datetime) -> datetime:
    """US-16: "12:40" (hora de Argentina) -> la proxima vez que sean las 12:40, en UTC.

    Si ya pasaron hoy, es manana (ej. a las 23:00 dice "01:00"). Hasta 16 horas: mas que eso es
    un error al escribirla.
    """
    horas, minutos = (int(parte) for parte in hora_fin.split(":"))
    local = ahora.astimezone(ZONA_ARGENTINA)
    fin = local.replace(hour=horas, minute=minutos, second=0, microsecond=0)
    if fin <= local:
        fin += timedelta(days=1)
    if fin - local > timedelta(hours=16):
        raise ErrorNegocio(422, "HORA_FIN_INVALIDA", "La hora hasta la que usás el aula tiene que ser dentro de las próximas 16 horas.")
    return fin.astimezone(ahora.tzinfo)


def crear_reserva(
    sesion: Session,
    usuario: Usuario,
    aula_id: int,
    ahora: datetime | None = None,
    hora_fin: str | None = None,
) -> Reserva:
    ahora = ahora or ahora_utc()
    fin = hora_fin_desde_texto(hora_fin, ahora) if hora_fin else None
    vencer_reservas(sesion, ahora)

    if reserva_activa(sesion, usuario, ahora) is not None:
        raise ErrorNegocio(
            409, "YA_TIENE_RESERVA", "Ya tenés una reserva pendiente. Usala o cancelala primero."
        )

    aula = sesion.get(Aula, aula_id)
    if aula is None:
        raise ErrorNegocio(404, "AULA_NO_ENCONTRADA", "El aula no existe.")

    # US-21: el equipo no pudo entregar esta llave y nadie lo reviso todavia
    if aula.id in aulas_en_revision(sesion):
        raise ErrorNegocio(
            409,
            "AULA_EN_REVISION",
            f"El aula {aula.nombre} está en revisión: el equipo no pudo entregar su llave. Pedila en portería.",
        )

    # US-22: sin equipo no hay como retirar la llave; no tiene sentido reservarla
    if not equipo_online(sesion, ahora):
        raise ErrorNegocio(
            409,
            "EQUIPO_DESCONECTADO",
            "El equipo de llaves está desconectado. Probá de nuevo en unos minutos.",
        )

    llave = sesion.scalar(
        select(Llave).where(Llave.aula_id == aula.id, Llave.estado != EstadoLlave.BAJA)
    )
    # UPDATE condicional: solo reserva la llave si en este momento sigue DISPONIBLE
    cambiadas = 0
    if llave is not None:
        cambiadas = sesion.execute(
            update(Llave)
            .where(Llave.id == llave.id, Llave.estado == EstadoLlave.DISPONIBLE)
            .values(estado=EstadoLlave.RESERVADA)
        ).rowcount
    if cambiadas != 1:
        raise ErrorNegocio(
            409, "LLAVE_NO_DISPONIBLE", f"La llave del aula {aula.nombre} no está disponible."
        )

    reserva = Reserva(
        usuario_id=usuario.id,
        llave_id=llave.id,
        codigo=_generar_codigo(sesion),
        creada_en=ahora,
        expira_en=ahora + timedelta(minutes=config.reserva_minutos),
        hora_fin=fin,
    )
    sesion.add(reserva)
    sesion.flush()  # para que la reserva tenga id
    return reserva


def reserva_activa(sesion: Session, usuario: Usuario, ahora: datetime | None = None) -> Reserva | None:
    """La reserva pendiente (y no vencida) del usuario, o None."""
    return sesion.scalar(
        select(Reserva).where(
            Reserva.usuario_id == usuario.id,
            Reserva.estado == EstadoReserva.PENDIENTE,
            Reserva.expira_en > (ahora or ahora_utc()),
        )
    )


def reserva_del_usuario(sesion: Session, usuario: Usuario, reserva_id: int) -> Reserva:
    """Una reserva del usuario, en cualquier estado (la web la consulta para saber si ya se uso)."""
    vencer_reservas(sesion)
    reserva = sesion.get(Reserva, reserva_id)
    # Una reserva de otro usuario se trata como inexistente: no se revela que existe
    if reserva is None or reserva.usuario_id != usuario.id:
        raise ErrorNegocio(404, "RESERVA_NO_ENCONTRADA", "La reserva no existe.")
    return reserva


def cancelar_reserva(sesion: Session, usuario: Usuario, reserva_id: int) -> None:
    reserva = reserva_del_usuario(sesion, usuario, reserva_id)
    if not _cerrar_reserva(sesion, reserva, EstadoReserva.CANCELADA):
        raise ErrorNegocio(
            409, "RESERVA_NO_PENDIENTE", "La reserva ya no está pendiente (se usó o venció)."
        )


def _cerrar_reserva(sesion: Session, reserva: Reserva, estado_final: EstadoReserva) -> bool:
    """Pasa una reserva PENDIENTE a estado_final y devuelve su llave a DISPONIBLE.

    Devuelve False si la reserva ya no estaba pendiente (otro pedido la cerro antes).
    """
    cambiadas = sesion.execute(
        update(Reserva)
        .where(Reserva.id == reserva.id, Reserva.estado == EstadoReserva.PENDIENTE)
        .values(estado=estado_final)
    ).rowcount
    if cambiadas != 1:
        return False
    sesion.execute(
        update(Llave)
        .where(Llave.id == reserva.llave_id, Llave.estado == EstadoLlave.RESERVADA)
        .values(estado=EstadoLlave.DISPONIBLE)
    )
    sesion.refresh(reserva)
    return True


def _generar_codigo(sesion: Session) -> str:
    """Codigo de 6 digitos que no repita el de otra reserva pendiente."""
    for _ in range(20):
        codigo = f"{secrets.randbelow(1_000_000):06d}"
        repetido = sesion.scalar(
            select(Reserva.id).where(
                Reserva.codigo == codigo, Reserva.estado == EstadoReserva.PENDIENTE
            )
        )
        if repetido is None:
            return codigo
    raise ErrorNegocio(500, "ERROR_INTERNO", "No se pudo generar un código. Probá de nuevo.")
