"""Tests de incidentes del equipo (US-05 y US-21): el preceptor ve las fallas al entregar una llave
y las marca resueltas."""

import itertools
import json
from datetime import timedelta

from sqlalchemy import select, update

from app import protocolo
from app.modelos import Aula, Incidente, Usuario
from app.servicios import incidentes, reservas
from app.tipos import ahora_utc

EQUIPO = "equipo-01"
ANA = "ana.perez@example.com"
CARLA_PRECEPTORA = "carla.diaz@example.com"
_contador = itertools.count(1)


def enviar_error(fabrica_sesiones, event_id=None, **datos):
    event_id = event_id or f"{EQUIPO}-inc-{next(_contador):04d}"
    crudo = json.dumps({"eventId": event_id, **datos}).encode()
    with fabrica_sesiones() as s:
        return protocolo.procesar_evento(s, EQUIPO, "error", crudo)


def reservar_214_para_ana(fabrica_sesiones) -> str:
    with fabrica_sesiones() as s:
        ana = s.scalar(select(Usuario).where(Usuario.email == ANA))
        aula_id = s.scalar(select(Aula.id).where(Aula.nombre == "214"))
        codigo = reservas.crear_reserva(s, ana, aula_id).codigo
        s.commit()
        return codigo


def todos(fabrica_sesiones) -> list[Incidente]:
    with fabrica_sesiones() as s:
        return list(s.scalars(select(Incidente)))


def test_error_con_codigo_registra_aula_y_docente(fabrica_sesiones):
    codigo = reservar_214_para_ana(fabrica_sesiones)
    res = enviar_error(fabrica_sesiones, error="LLAVE_NO_ENCONTRADA", codigo=codigo, detalle="slot 1")
    assert res["ok"] is True

    with fabrica_sesiones() as s:
        incidente = s.scalar(select(Incidente))
        assert incidente.tipo == "LLAVE_NO_ENCONTRADA" and incidente.detalle == "slot 1"
        assert incidente.aula.nombre == "214" and incidente.usuario.apellido == "Perez"


def test_error_sin_codigo_igual_queda_registrado(fabrica_sesiones):
    # Ej. el homing no encontro el tag HOME al arrancar: no hay reserva de por medio
    assert enviar_error(fabrica_sesiones, error="MOTOR_NO_GIRA")["ok"] is True
    (incidente,) = todos(fabrica_sesiones)
    assert incidente.aula_id is None and incidente.usuario_id is None


def test_error_repetido_no_duplica_el_incidente(fabrica_sesiones):
    for _ in range(2):  # el equipo reintenta con el mismo eventId si no le llega la respuesta
        enviar_error(fabrica_sesiones, event_id="equipo-01-inc-repetido", error="MOTOR_NO_GIRA")
    assert len(todos(fabrica_sesiones)) == 1


def test_error_con_datos_invalidos_no_registra_nada(fabrica_sesiones):
    res = enviar_error(fabrica_sesiones, error="LLAVE_NO_ENCONTRADA", codigo="12")
    assert res == {"eventId": res["eventId"], "ok": False, "motivo": "DATOS_INVALIDOS"}
    assert todos(fabrica_sesiones) == []


def test_preceptor_ve_los_incidentes_de_hoy(cliente, ingresar, fabrica_sesiones):
    codigo = reservar_214_para_ana(fabrica_sesiones)
    enviar_error(fabrica_sesiones, error="MOTOR_NO_GIRA")
    enviar_error(fabrica_sesiones, error="LLAVE_NO_ENCONTRADA", codigo=codigo)
    ingresar(CARLA_PRECEPTORA)

    lista = cliente.get("/api/incidentes").json()
    # Del mas nuevo al mas viejo
    assert [i["descripcion"] for i in lista] == ["Llave no encontrada", "Motor no gira"]
    assert lista[0]["aula"] == "214" and lista[0]["docente"] == "Ana Perez"
    assert lista[1]["aula"] is None and lista[1]["docente"] is None


def test_los_de_ayer_solo_aparecen_si_siguen_abiertos(cliente, ingresar, fabrica_sesiones):
    enviar_error(fabrica_sesiones, error="MOTOR_NO_GIRA")
    enviar_error(fabrica_sesiones, error="LLAVE_NO_ENCONTRADA")
    ayer = ahora_utc() - timedelta(days=1)
    with fabrica_sesiones() as s:
        s.execute(update(Incidente).values(ocurrido_en=ayer))
        s.execute(update(Incidente).where(Incidente.tipo == "LLAVE_NO_ENCONTRADA").values(resuelto_en=ayer))
        s.commit()
    ingresar(CARLA_PRECEPTORA)
    assert [i["tipo"] for i in cliente.get("/api/incidentes").json()] == ["MOTOR_NO_GIRA"]


def test_hoy_es_el_dia_de_argentina(sesion):
    medianoche_utc = ahora_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    # Resueltos: solo aparecen si son de hoy
    ayer_23_utc = Incidente(
        device_id=EQUIPO, tipo="A", ocurrido_en=medianoche_utc - timedelta(hours=1), resuelto_en=medianoche_utc
    )
    hoy_02_utc = Incidente(
        device_id=EQUIPO, tipo="B", ocurrido_en=medianoche_utc + timedelta(hours=2), resuelto_en=medianoche_utc
    )
    sesion.add_all([ayer_23_utc, hoy_02_utc])
    sesion.flush()

    # A las 02:30 UTC son las 23:30 en Argentina: las 23:00 UTC de "ayer" (20:00 en Argentina)
    # todavia son de hoy
    a_las_0230 = medianoche_utc + timedelta(hours=2, minutes=30)
    assert {i.tipo for i in incidentes.abiertos_y_de_hoy(sesion, a_las_0230)} == {"A", "B"}

    # A las 04:00 UTC ya es la 01:00 del dia siguiente en Argentina: los dos quedaron en "ayer"
    a_las_0400 = medianoche_utc + timedelta(hours=4)
    assert incidentes.abiertos_y_de_hoy(sesion, a_las_0400) == []


def test_docente_no_ve_los_incidentes(cliente, ingresar):
    ingresar(ANA)
    res = cliente.get("/api/incidentes")
    assert res.status_code == 403 and res.json()["error"]["codigo"] == "SIN_PERMISO"


def test_tipo_desconocido_se_muestra_legible():
    assert incidentes.descripcion("LECTOR_RFID_NO_RESPONDE") == "Lector rfid no responde"


# --- US-21: incidentes abiertos y resueltos ---


def aula_214(cliente):
    return next(a for a in cliente.get("/api/publico/estado").json()["aulas"] if a["nombre"] == "214")


def test_con_un_incidente_abierto_el_aula_queda_en_revision(cliente, ingresar, fabrica_sesiones):
    codigo = reservar_214_para_ana(fabrica_sesiones)
    enviar_error(fabrica_sesiones, error="LLAVE_NO_ENCONTRADA", codigo=codigo)
    with fabrica_sesiones() as s:  # la reserva vence sola: la llave vuelve a estar DISPONIBLE
        reservas.cancelar_reserva(s, s.scalar(select(Usuario).where(Usuario.email == ANA)), 1)
        s.commit()

    assert aula_214(cliente)["estado"] == "EN_REVISION"
    ingresar(ANA)
    res = cliente.post("/api/reservas", json={"aulaId": aula_214(cliente)["id"]})
    assert res.status_code == 409 and res.json()["error"]["codigo"] == "AULA_EN_REVISION"


def test_el_preceptor_lo_resuelve_y_el_aula_vuelve(cliente, ingresar, fabrica_sesiones):
    codigo = reservar_214_para_ana(fabrica_sesiones)
    enviar_error(fabrica_sesiones, error="LLAVE_NO_ENCONTRADA", codigo=codigo)
    with fabrica_sesiones() as s:
        reservas.cancelar_reserva(s, s.scalar(select(Usuario).where(Usuario.email == ANA)), 1)
        s.commit()
    ingresar(CARLA_PRECEPTORA)
    incidente = cliente.get("/api/incidentes").json()[0]

    res = cliente.post(f"/api/incidentes/{incidente['id']}/resolver")
    assert res.status_code == 200
    assert res.json()["resueltoEn"] is not None and res.json()["resueltoPor"] == "Carla Diaz"
    assert aula_214(cliente)["estado"] == "DISPONIBLE"
    # Resolverlo de nuevo no cambia nada (dos preceptores a la vez)
    assert cliente.post(f"/api/incidentes/{incidente['id']}/resolver").json() == res.json()


def test_un_incidente_sin_aula_no_bloquea_ninguna(cliente, fabrica_sesiones):
    enviar_error(fabrica_sesiones, error="MOTOR_NO_GIRA")
    estados = {a["estado"] for a in cliente.get("/api/publico/estado").json()["aulas"]}
    assert "EN_REVISION" not in estados


def test_docente_no_resuelve_incidentes(cliente, ingresar, fabrica_sesiones):
    enviar_error(fabrica_sesiones, error="MOTOR_NO_GIRA")
    ingresar(ANA)
    assert cliente.post("/api/incidentes/1/resolver").status_code == 403


def test_resolver_uno_que_no_existe(cliente, ingresar):
    ingresar(CARLA_PRECEPTORA)
    res = cliente.post("/api/incidentes/999/resolver")
    assert res.status_code == 404 and res.json()["error"]["codigo"] == "INCIDENTE_NO_ENCONTRADO"
