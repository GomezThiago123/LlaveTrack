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

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from pydantic.alias_generators import to_camel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import EventoDispositivo
from app.servicios import conexion, equipo, incidentes
from app.servicios.equipo import RechazoEquipo
from app.servicios.reservas import vencer_reservas

log = logging.getLogger(__name__)

# Los servicios dejan aca (sesion.info) lo que hay que hacer recien despues del commit, como mandar
# un mail: si el evento se rechaza o falla, no se hace
DESPUES_DEL_COMMIT = equipo.DESPUES_DEL_COMMIT


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
    # El codigo de la reserva o, en su lugar, el DNI del docente (US-18): uno de los dos
    codigo: str | None = Field(default=None, pattern=r"^\d{6}$")
    dni: str | None = Field(default=None, pattern=r"^\d{7,8}$")

    @model_validator(mode="after")
    def codigo_o_dni(self):
        if (self.codigo is None) == (self.dni is None):
            raise ValueError("hace falta el codigo o el dni (uno solo)")
        return self


class RetiroInterrumpido(Evento):
    """US-15: se corto la luz durante este retiro. La reserva se cancela."""

    codigo: str = Field(pattern=r"^\d{6}$")


class RetiroConfirmado(ConUid):
    codigo: str = Field(pattern=r"^\d{6}$")
    slot: int = Field(ge=0)


class RetiroTimeout(Evento):
    codigo: str = Field(pattern=r"^\d{6}$")


class Devolucion(ConUid):
    slot: int = Field(ge=0)
    # US-20: quien devuelve se identifica con su DNI (opcional). Si no es quien la retiro, el
    # servidor pide confirmacion (CONFIRMAR_TERCERO) y el equipo la reenvia con confirmada=true
    dni: str | None = Field(default=None, pattern=r"^\d{7,8}$")
    confirmada: bool = False
    # US-14: la devolucion se hizo sin conexion; la hora real (segundos desde 1970, UTC)
    devuelto_en: int | None = Field(default=None, ge=0)


class TagLeido(ConUid):
    """US-10, modo alta: el equipo leyo este tag en la ventana."""

    slot: int = Field(ge=0)


class ErrorDelEquipo(Evento):
    error: str = Field(min_length=1, max_length=40)  # LLAVE_NO_ENCONTRADA, MOTOR_NO_GIRA, ...
    codigo: str | None = Field(default=None, pattern=r"^\d{6}$")  # la reserva que se estaba entregando
    detalle: str | None = Field(default=None, max_length=200)


FORMATOS: dict[str, type[Evento]] = {
    "inicio": Inicio,
    "solicitud_retiro": SolicitudRetiro,
    "retiro_confirmado": RetiroConfirmado,
    "retiro_timeout": RetiroTimeout,
    "devolucion": Devolucion,
    "error": ErrorDelEquipo,
    "retiro_interrumpido": RetiroInterrumpido,
    "tag_leido": TagLeido,
}


def _ejecutar(sesion: Session, device_id: str, tipo: str, evento) -> dict:
    """Llama al servicio que corresponde. Devuelve los datos extra de la respuesta."""
    match tipo:
        case "inicio":
            return equipo.inicio(sesion, device_id, evento.slots_totales, evento.slots_reservados)
        case "solicitud_retiro":
            return equipo.solicitud_retiro(sesion, evento.codigo, dni=evento.dni)
        case "retiro_confirmado":
            return equipo.retiro_confirmado(sesion, evento.codigo, evento.uid, evento.slot)
        case "retiro_timeout":
            # La reserva sigue vigente hasta que vence: solo queda registrado en el log
            return {}
        case "devolucion":
            return equipo.devolucion(
                sesion,
                device_id,
                evento.uid,
                evento.slot,
                dni=evento.dni,
                confirmada=evento.confirmada,
                devuelto_en=evento.devuelto_en,
            )
        case "retiro_interrumpido":
            return equipo.retiro_interrumpido(sesion, evento.codigo)
        case "tag_leido":
            return equipo.tag_leido(sesion, device_id, evento.uid, evento.slot)
        case "error":
            # US-05: queda como incidente para el preceptor
            log.warning("Error informado por %s: %s (%s)", device_id, evento.error, evento.detalle)
            incidentes.registrar(sesion, device_id, evento.error, evento.codigo, evento.detalle)
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
        conexion.registrar_contacto(sesion, device_id)
        # Se guarda aunque despues el evento se rechace (ej. CODIGO_VENCIDO)
        vencer_reservas(sesion)
        try:
            # Savepoint: si el evento se rechaza, se deshace solo lo que hizo el evento
            with sesion.begin_nested():
                extra = _ejecutar(sesion, device_id, tipo, evento)
            respuesta = {"eventId": event_id, "ok": True, **extra}
        except RechazoEquipo as rechazo:
            respuesta = {**_rechazo(event_id, rechazo.motivo), **rechazo.datos}
            sesion.info.pop(DESPUES_DEL_COMMIT, None)  # lo del evento se deshizo
        except Exception:
            # Error inesperado: no se guarda el evento, asi el reintento del equipo lo procesa de nuevo
            log.exception("Error procesando %s", event_id)
            sesion.rollback()
            sesion.info.pop(DESPUES_DEL_COMMIT, None)
            return _rechazo(event_id, "ERROR_INTERNO")

    sesion.add(
        EventoDispositivo(
            event_id=event_id, device_id=device_id, tipo=tipo, payload=datos, respuesta=respuesta
        )
    )
    sesion.commit()
    # Lo que tiene que pasar solo si el evento quedo guardado (ej. US-20: el mail al docente)
    for accion in sesion.info.pop(DESPUES_DEL_COMMIT, []):
        try:
            accion()
        except Exception:
            log.exception("Fallo una accion posterior a %s", event_id)
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
    conexion.registrar_contacto(sesion, device_id, online=online)
    sesion.commit()
    log.info("Equipo %s %s", device_id, "online" if online else "OFFLINE")


def procesar_latido(sesion: Session, device_id: str) -> None:
    """Mensaje de `latido` (cada 30 s): el equipo sigue vivo. No lleva eventId ni respuesta."""
    conexion.registrar_contacto(sesion, device_id)
    sesion.commit()


def _rechazo(event_id: str, motivo: str) -> dict:
    return {"eventId": event_id, "ok": False, "motivo": motivo}
