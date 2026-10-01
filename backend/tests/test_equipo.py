"""Tests de los eventos del equipo: inicio, retiro (US-04/05) y devolucion (US-06).

Llaman directo a procesar_evento, sin broker MQTT: prueban la logica, no la red.
"""

import itertools
import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from app import protocolo
from app.modelos import (
    Aula,
    Dispositivo,
    EstadoLlave,
    EstadoReserva,
    EventoDispositivo,
    Llave,
    Prestamo,
    Reserva,
    Usuario,
)
from app.servicios import equipo, reservas
from app.tipos import ahora_utc

EQUIPO = "equipo-01"
UID_214 = "04A1B2C3"  # llave del aula 214, en el slot 1 (seed/datos.json)
_contador = itertools.count(1)


def enviar(fabrica_sesiones, tipo, event_id=None, **datos):
    """Simula un mensaje del equipo. Devuelve la respuesta del servidor."""
    event_id = event_id or f"{EQUIPO}-test-{next(_contador):04d}"
    crudo = json.dumps({"eventId": event_id, **datos}).encode()
    with fabrica_sesiones() as s:
        return protocolo.procesar_evento(s, EQUIPO, tipo, crudo)


def reservar(fabrica_sesiones, email="ana.perez@example.com", aula="214", ahora=None) -> str:
    """Crea una reserva y devuelve su codigo."""
    with fabrica_sesiones() as s:
        usuario = s.scalar(select(Usuario).where(Usuario.email == email))
        aula_id = s.scalar(select(Aula.id).where(Aula.nombre == aula))
        codigo = reservas.crear_reserva(s, usuario, aula_id, ahora=ahora).codigo
        s.commit()
        return codigo


def llave_214(fabrica_sesiones) -> Llave:
    with fabrica_sesiones() as s:
        return s.scalar(select(Llave).where(Llave.rfid_uid == UID_214))


def contar(fabrica_sesiones, modelo) -> int:
    with fabrica_sesiones() as s:
        return len(s.scalars(select(modelo)).all())


# --- Inicio ---


def test_inicio_marca_online_y_devuelve_el_slot_vacio_mas_cercano(fabrica_sesiones):
    # Slot 0 reservado (HOME) y slots 1 a 5 con llaves: el vacio mas cercano al 0 es el 23
    res = enviar(fabrica_sesiones, "inicio", slotsTotales=24, slotsReservados=[0])
    assert res["ok"] is True
    assert res["slotReposo"] == 23
    with fabrica_sesiones() as s:
        assert s.scalar(select(Dispositivo.online).where(Dispositivo.device_id == EQUIPO)) is True


# --- Retiro ---


def test_codigo_valido_dice_que_llave_entregar(fabrica_sesiones):
    codigo = reservar(fabrica_sesiones)
    res = enviar(fabrica_sesiones, "solicitud_retiro", codigo=codigo)
    assert res == {
        "eventId": res["eventId"],
        "ok": True,
        "slot": 1,
        "uid": UID_214,
        "aula": "214",
        "apellido": "Perez",
    }


def test_codigo_inexistente(fabrica_sesiones):
    res = enviar(fabrica_sesiones, "solicitud_retiro", codigo="000000")
    assert res["ok"] is False and res["motivo"] == "CODIGO_INVALIDO"


def test_codigo_vencido(fabrica_sesiones):
    codigo = reservar(fabrica_sesiones, ahora=ahora_utc() - timedelta(minutes=11))
    res = enviar(fabrica_sesiones, "solicitud_retiro", codigo=codigo)
    assert res["motivo"] == "CODIGO_VENCIDO"
    assert llave_214(fabrica_sesiones).estado == EstadoLlave.DISPONIBLE


def test_codigo_aceptado_extiende_la_reserva_para_que_no_venza_durante_el_retiro(fabrica_sesiones):
    # Reserva a la que le quedan ~30 segundos
    codigo = reservar(fabrica_sesiones, ahora=ahora_utc() - timedelta(minutes=9, seconds=30))
    enviar(fabrica_sesiones, "solicitud_retiro", codigo=codigo)
    with fabrica_sesiones() as s:
        reserva = s.scalar(select(Reserva).where(Reserva.codigo == codigo))
        assert reserva.expira_en >= ahora_utc() + timedelta(seconds=110)


def test_ciclo_completo_retiro_y_devolucion(fabrica_sesiones):
    codigo = reservar(fabrica_sesiones)
    assert enviar(fabrica_sesiones, "solicitud_retiro", codigo=codigo)["ok"]

    res = enviar(fabrica_sesiones, "retiro_confirmado", codigo=codigo, uid=UID_214, slot=1)
    assert res["ok"] is True
    llave = llave_214(fabrica_sesiones)
    assert llave.estado == EstadoLlave.PRESTADA and llave.slot is None
    with fabrica_sesiones() as s:
        assert s.scalar(select(Reserva.estado).where(Reserva.codigo == codigo)) == EstadoReserva.USADA
        prestamo = s.scalar(select(Prestamo))
        assert prestamo.devuelto_en is None and prestamo.usuario.apellido == "Perez"

    # La cuelga en el slot 1 (el que quedo vacio)
    res = enviar(fabrica_sesiones, "devolucion", uid=UID_214, slot=1)
    assert res["ok"] is True
    assert res["aula"] == "214" and res["apellido"] == "Perez"
    assert res["slotReposo"] == 23  # vacio mas cercano al 1 (el 0 es HOME, del 2 al 5 hay llaves)
    llave = llave_214(fabrica_sesiones)
    assert llave.estado == EstadoLlave.DISPONIBLE and llave.slot == 1
    with fabrica_sesiones() as s:
        assert s.scalar(select(Prestamo)).devuelto_en is not None


def test_devolucion_en_otro_slot_actualiza_la_posicion(fabrica_sesiones):
    codigo = reservar(fabrica_sesiones)
    enviar(fabrica_sesiones, "retiro_confirmado", codigo=codigo, uid=UID_214, slot=1)
    enviar(fabrica_sesiones, "devolucion", uid=UID_214, slot=10)
    assert llave_214(fabrica_sesiones).slot == 10


def test_retiro_con_uid_que_no_corresponde_no_cambia_nada(fabrica_sesiones):
    codigo = reservar(fabrica_sesiones)
    res = enviar(fabrica_sesiones, "retiro_confirmado", codigo=codigo, uid="04B2C3D4", slot=2)
    assert res["motivo"] == "CODIGO_INVALIDO"
    assert llave_214(fabrica_sesiones).estado == EstadoLlave.RESERVADA
    assert contar(fabrica_sesiones, Prestamo) == 0


def test_retiro_timeout_deja_la_reserva_vigente(fabrica_sesiones):
    codigo = reservar(fabrica_sesiones)
    enviar(fabrica_sesiones, "solicitud_retiro", codigo=codigo)
    assert enviar(fabrica_sesiones, "retiro_timeout", codigo=codigo)["ok"] is True
    # Puede volver a intentar con el mismo codigo
    assert enviar(fabrica_sesiones, "solicitud_retiro", codigo=codigo)["ok"] is True


# --- Devolucion rechazada ---


def test_devolucion_de_llave_desconocida(fabrica_sesiones):
    res = enviar(fabrica_sesiones, "devolucion", uid="DEADBEEF", slot=1)
    assert res["motivo"] == "LLAVE_DESCONOCIDA"


def test_devolucion_de_llave_que_no_estaba_prestada(fabrica_sesiones):
    res = enviar(fabrica_sesiones, "devolucion", uid=UID_214, slot=7)
    assert res["motivo"] == "SIN_PRESTAMO_ACTIVO"
    assert llave_214(fabrica_sesiones).slot == 1  # no se registro nada


# --- Duplicados y datos invalidos ---


def test_evento_repetido_devuelve_la_misma_respuesta_sin_procesar_dos_veces(fabrica_sesiones):
    codigo = reservar(fabrica_sesiones)
    primera = enviar(fabrica_sesiones, "retiro_confirmado", "equipo-01-abcd-0001", codigo=codigo, uid=UID_214, slot=1)
    segunda = enviar(fabrica_sesiones, "retiro_confirmado", "equipo-01-abcd-0001", codigo=codigo, uid=UID_214, slot=1)
    assert primera == segunda and primera["ok"] is True
    assert contar(fabrica_sesiones, Prestamo) == 1
    assert contar(fabrica_sesiones, EventoDispositivo) == 1


def test_rechazo_repetido_devuelve_el_mismo_rechazo(fabrica_sesiones):
    primera = enviar(fabrica_sesiones, "solicitud_retiro", "equipo-01-abcd-0002", codigo="000000")
    segunda = enviar(fabrica_sesiones, "solicitud_retiro", "equipo-01-abcd-0002", codigo="000000")
    assert primera == segunda and primera["motivo"] == "CODIGO_INVALIDO"


def test_uid_con_separadores_y_minusculas_se_normaliza(fabrica_sesiones):
    codigo = reservar(fabrica_sesiones)
    res = enviar(fabrica_sesiones, "retiro_confirmado", codigo=codigo, uid="04:a1:b2:c3", slot=1)
    assert res["ok"] is True


@pytest.mark.parametrize(
    ("tipo", "datos"),
    [
        ("solicitud_retiro", {"codigo": "12ab56"}),
        ("solicitud_retiro", {}),
        ("devolucion", {"uid": "no-es-hex", "slot": 1}),
        ("devolucion", {"uid": UID_214, "slot": -1}),
        ("tipo_que_no_existe", {}),
    ],
)
def test_datos_invalidos(fabrica_sesiones, tipo, datos):
    res = enviar(fabrica_sesiones, tipo, **datos)
    assert res["ok"] is False and res["motivo"] == "DATOS_INVALIDOS"


def test_json_ilegible_no_se_responde(fabrica_sesiones):
    with fabrica_sesiones() as s:
        assert protocolo.procesar_evento(s, EQUIPO, "solicitud_retiro", b"{no es json") is None
        assert protocolo.procesar_evento(s, EQUIPO, "solicitud_retiro", b'{"codigo":"123456"}') is None


def test_error_interno_no_se_guarda_para_que_el_reintento_lo_procese(fabrica_sesiones, monkeypatch):
    codigo = reservar(fabrica_sesiones)

    def falla(*_args, **_kwargs):
        raise RuntimeError("se cayo algo")

    monkeypatch.setattr(equipo, "solicitud_retiro", falla)
    res = enviar(fabrica_sesiones, "solicitud_retiro", "equipo-01-abcd-0003", codigo=codigo)
    assert res["motivo"] == "ERROR_INTERNO"
    assert contar(fabrica_sesiones, EventoDispositivo) == 0

    monkeypatch.undo()
    res = enviar(fabrica_sesiones, "solicitud_retiro", "equipo-01-abcd-0003", codigo=codigo)
    assert res["ok"] is True


# --- Online / offline ---


def test_estado_online_y_offline(fabrica_sesiones):
    def online():
        with fabrica_sesiones() as s:
            return s.scalar(select(Dispositivo.online).where(Dispositivo.device_id == EQUIPO))

    with fabrica_sesiones() as s:
        protocolo.procesar_estado(s, EQUIPO, b'{"online": true}')
    assert online() is True
    with fabrica_sesiones() as s:
        protocolo.procesar_estado(s, EQUIPO, b'{"online": false}')
    assert online() is False


def test_rechazo_deshace_los_cambios_a_medias_pero_no_el_vencimiento(fabrica_sesiones, monkeypatch):
    vieja = reservar(fabrica_sesiones, aula="215", ahora=ahora_utc() - timedelta(minutes=11))

    def cambia_y_rechaza(sesion, *_args):
        sesion.scalar(select(Llave).where(Llave.rfid_uid == UID_214)).slot = 99
        sesion.flush()
        raise equipo.RechazoEquipo("CODIGO_INVALIDO")

    monkeypatch.setattr(equipo, "solicitud_retiro", cambia_y_rechaza)
    assert enviar(fabrica_sesiones, "solicitud_retiro", codigo="123456")["ok"] is False

    assert llave_214(fabrica_sesiones).slot == 1  # el cambio a medias se deshizo
    with fabrica_sesiones() as s:  # el vencimiento de la otra reserva se guardo
        assert s.scalar(select(Reserva.estado).where(Reserva.codigo == vieja)) == EstadoReserva.VENCIDA
