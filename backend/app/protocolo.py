"""Procesa los mensajes MQTT del equipo (contrato en docs/protocolo-mqtt.md).

Por cada evento:
1. Valida el JSON con Pydantic.
2. Si el eventId ya se proceso, devuelve la MISMA respuesta que la primera vez, sin repetir
   nada (el equipo reintenta si no le llego la respuesta).
3. Llama al servicio que corresponde y guarda el evento junto con su respuesta, en la
   misma transaccion que los cambios: o se guarda todo o no se guarda nada.
"""

import json
import logging
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic.alias_generators import to_camel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import EventoDispositivo
from app.servicios import equipo
from app.servicios.equipo import RechazoEquipo
from app.servicios.reservas import vencer_reservas

log = logging.getLogger(__name__)


# --- Formato de cada evento ---


class Evento(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    event_id: str = Field(min_length=1, max_length=80)


class ConUid(Evento):
    uid: str

    @field_validator("uid")
    @classmethod
    def normalizar_uid(cls, uid: str) -> str:
        # Hex en mayusculas y sin separadores: "04:a1:b2:c3" -> "04A1B2C3"
        uid = re.sub(r"[\s:-]", "", uid).upper()
        if not re.fullmatch(r"[0-9A-F]{8,20}", uid):
            raise ValueError("UID invalido")
        return uid


class Inicio(Evento):
    slots_totales: int = Field(ge=1, le=200)
    slots_reservados: list[int] = []


class SolicitudRetiro(Evento):
    codigo: str = Field(pattern=r"^\d{6}$")


class RetiroConfirmado(ConUid):
    codigo: str = Field(pattern=r"^\d{6}$")
    slot: int = Field(ge=0)


class RetiroTimeout(Evento):
    codigo: str = Field(pattern=r"^\d{6}$")


class Devolucion(ConUid):
    slot: int = Field(ge=0)


class ErrorDelEquipo(Evento):
    error: str
    detalle: str | None = None


FORMATOS: dict[str, type[Evento]] = {
    "inicio": Inicio,
    "solicitud_retiro": SolicitudRetiro,
    "retiro_confirmado": RetiroConfirmado,
    "retiro_timeout": RetiroTimeout,
    "devolucion": Devolucion,
    "error": ErrorDelEquipo,
}


def _ejecutar(sesion: Session, device_id: str, tipo: str, evento) -> dict:
    """Llama al servicio que corresponde. Devuelve los datos extra de la respuesta."""
    match tipo:
        case "inicio":
            return equipo.inicio(sesion, device_id, evento.slots_totales, evento.slots_reservados)
        case "solicitud_retiro":
            return equipo.solicitud_retiro(sesion, evento.codigo)
        case "retiro_confirmado":
            return equipo.retiro_confirmado(sesion, evento.codigo, evento.uid, evento.slot)
        case "retiro_timeout":
            # La reserva sigue vigente hasta que vence: solo queda registrado en el log
            return {}
        case "devolucion":
            return equipo.devolucion(sesion, device_id, evento.uid, evento.slot)
        case "error":
            log.warning("Error informado por %s: %s (%s)", device_id, evento.error, evento.detalle)
            return {}
    raise AssertionError(tipo)


# --- Punto de entrada ---


def procesar_evento(sesion: Session, device_id: str, tipo: str, crudo: bytes) -> dict | None:
    """Procesa un evento y devuelve la respuesta a publicar en `resp`.

    Devuelve None si no se puede responder (JSON roto o sin eventId).
    Hace commit: cada evento es una transaccion completa.
    """
    try:
        datos = json.loads(crudo)
        event_id = datos["eventId"]
        if not isinstance(event_id, str) or not event_id:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        log.warning("Evento ilegible de %s/%s: %r", device_id, tipo, crudo[:200])
        return None

    # Duplicado: misma respuesta que la primera vez, sin volver a procesar
    anterior = sesion.scalar(select(EventoDispositivo).where(EventoDispositivo.event_id == event_id))
    if anterior is not None:
        log.info("Evento repetido %s: se reenvia la respuesta guardada", event_id)
        return anterior.respuesta

    formato = FORMATOS.get(tipo)
    try:
        evento = formato.model_validate(datos) if formato else None
    except ValidationError as error:
        log.warning("Evento %s con datos invalidos: %s", event_id, error)
        evento = None

    if evento is None:
        respuesta = _rechazo(event_id, "DATOS_INVALIDOS")
    else:
        equipo.registrar_contacto(sesion, device_id)
        # Se guarda aunque despues el evento se rechace (ej. CODIGO_VENCIDO)
        vencer_reservas(sesion)
        try:
            # Savepoint: si el evento se rechaza, se deshace solo lo que hizo el evento
            with sesion.begin_nested():
                extra = _ejecutar(sesion, device_id, tipo, evento)
            respuesta = {"eventId": event_id, "ok": True, **extra}
        except RechazoEquipo as rechazo:
            respuesta = _rechazo(event_id, rechazo.motivo)
        except Exception:
            # Error inesperado: no se guarda el evento, asi el reintento del equipo lo procesa de nuevo
            log.exception("Error procesando %s", event_id)
            sesion.rollback()
            return _rechazo(event_id, "ERROR_INTERNO")

    sesion.add(
        EventoDispositivo(
            event_id=event_id, device_id=device_id, tipo=tipo, payload=datos, respuesta=respuesta
        )
    )
    sesion.commit()
    return respuesta


def procesar_estado(sesion: Session, device_id: str, crudo: bytes) -> None:
    """Mensaje retenido de `estado`: {"online": true} al conectar, {"online": false} (LWT) al caer."""
    try:
        online = json.loads(crudo)["online"]
        if not isinstance(online, bool):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        log.warning("Estado ilegible de %s: %r", device_id, crudo[:200])
        return
    equipo.registrar_contacto(sesion, device_id, online=online)
    sesion.commit()
    log.info("Equipo %s %s", device_id, "online" if online else "OFFLINE")


def _rechazo(event_id: str, motivo: str) -> dict:
    return {"eventId": event_id, "ok": False, "motivo": motivo}
