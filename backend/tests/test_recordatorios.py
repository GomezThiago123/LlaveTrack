"""US-16: el docente dice hasta que hora usa el aula; si no devuelve la llave, le llega un aviso
a los 15 minutos y el preceptor la ve "Demorada" a la hora."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import correo, tareas
from app.errores import ErrorNegocio
from app.modelos import Aula, Llave, Prestamo, Reserva, Usuario
from app.servicios import recordatorios, reservas
from app.servicios.reservas import hora_fin_desde_texto
from app.tipos import ZONA_ARGENTINA, ahora_utc

ANA = "ana.perez@example.com"
CARLA = "carla.diaz@example.com"


def en_argentina(hora: int, minuto: int = 0) -> datetime:
    """Hoy a esa hora en Argentina, en UTC."""
    hoy = ahora_utc().astimezone(ZONA_ARGENTINA)
    return hoy.replace(hour=hora, minute=minuto, second=0, microsecond=0).astimezone(ahora_utc().tzinfo)


def test_la_hora_fin_es_la_proxima_vez_que_sea_esa_hora():
    a_las_10 = en_argentina(10)
    assert hora_fin_desde_texto("12:40", a_las_10) == en_argentina(12, 40)
    # A las 23:00 "01:00" es manana
    a_las_23 = en_argentina(23)
    assert hora_fin_desde_texto("01:00", a_las_23) == en_argentina(1) + timedelta(days=1)


def test_una_hora_fin_demasiado_lejana_se_rechaza():
    with pytest.raises(ErrorNegocio) as error:
        hora_fin_desde_texto("09:00", en_argentina(10))  # 23 horas despues
    assert error.value.codigo == "HORA_FIN_INVALIDA"


def test_la_reserva_guarda_la_hora_fin(cliente, ingresar, fabrica_sesiones):
    ingresar(ANA)
    aula_id = cliente.get("/api/aulas").json()[0]["id"]
    fin = (ahora_utc() + timedelta(hours=2)).astimezone(ZONA_ARGENTINA)
    res = cliente.post("/api/reservas", json={"aulaId": aula_id, "horaFin": f"{fin:%H:%M}"})
    assert res.status_code == 201, res.text
    assert res.json()["horaFin"] is not None


def test_una_hora_fin_mal_escrita_es_dato_invalido(cliente, ingresar):
    ingresar(ANA)
    aula_id = cliente.get("/api/aulas").json()[0]["id"]
    res = cliente.post("/api/reservas", json={"aulaId": aula_id, "horaFin": "25:99"})
    assert res.status_code == 422


def prestar_con_fin(fabrica_sesiones, fin: datetime, devuelto: bool = False) -> int:
    with fabrica_sesiones() as s:
        ana = s.scalar(select(Usuario).where(Usuario.email == ANA))
        llave = s.scalar(select(Llave).join(Aula).where(Aula.nombre == "214"))
        reserva = Reserva(usuario_id=ana.id, llave_id=llave.id, codigo="000000", expira_en=ahora_utc(), estado="USADA")
        s.add(reserva)
        s.flush()
        prestamo = Prestamo(
            llave_id=llave.id, usuario_id=ana.id, reserva_id=reserva.id,
            retirado_en=fin - timedelta(hours=1), hora_fin=fin,
            devuelto_en=ahora_utc() if devuelto else None,
        )
        s.add(prestamo)
        s.commit()
        return prestamo.id


def mails(monkeypatch) -> list:
    enviados = []
    monkeypatch.setattr(correo, "enviar_recordatorio", lambda usuario, aula: enviados.append((usuario.email, aula)))
    return enviados


def test_a_los_15_minutos_le_llega_el_aviso_una_sola_vez(fabrica_sesiones, monkeypatch):
    enviados = mails(monkeypatch)
    prestar_con_fin(fabrica_sesiones, ahora_utc() - timedelta(minutes=16))
    assert tareas.revisar_recordatorios(fabrica_sesiones) == 1
    assert enviados == [(ANA, "214")]
    # La vuelta siguiente no lo vuelve a mandar
    assert tareas.revisar_recordatorios(fabrica_sesiones) == 0


def test_antes_de_los_15_minutos_no_hay_aviso(fabrica_sesiones, monkeypatch):
    enviados = mails(monkeypatch)
    prestar_con_fin(fabrica_sesiones, ahora_utc() - timedelta(minutes=10))
    assert tareas.revisar_recordatorios(fabrica_sesiones) == 0 and enviados == []


def test_si_la_devolvio_no_hay_aviso(fabrica_sesiones, monkeypatch):
    enviados = mails(monkeypatch)
    prestar_con_fin(fabrica_sesiones, ahora_utc() - timedelta(minutes=30), devuelto=True)
    assert tareas.revisar_recordatorios(fabrica_sesiones) == 0 and enviados == []


def test_si_falla_el_mail_no_se_vuelve_a_intentar(fabrica_sesiones, monkeypatch):
    def falla(*_):
        raise OSError("sin conexion")

    monkeypatch.setattr(correo, "enviar_recordatorio", falla)
    prestar_con_fin(fabrica_sesiones, ahora_utc() - timedelta(minutes=20))
    assert tareas.revisar_recordatorios(fabrica_sesiones) == 1  # lo intento y no rompio el hilo
    assert tareas.revisar_recordatorios(fabrica_sesiones) == 0


def test_el_preceptor_la_ve_demorada_a_la_hora(cliente, ingresar, fabrica_sesiones):
    demorada_id = prestar_con_fin(fabrica_sesiones, ahora_utc() - timedelta(minutes=61))
    ingresar(CARLA)
    prestamos = {p["id"]: p for p in cliente.get("/api/prestamos", params={"estado": "abiertos"}).json()["prestamos"]}
    assert prestamos[demorada_id]["demorada"] is True
    with fabrica_sesiones() as s:
        prestamo = s.get(Prestamo, demorada_id)
        assert recordatorios.demorada(prestamo, prestamo.hora_fin + timedelta(minutes=59)) is False


def test_el_retiro_copia_la_hora_fin_al_prestamo(fabrica_sesiones):
    """retiro_confirmado (equipo) pasa la hora fin de la reserva al prestamo."""
    import json

    from app import protocolo

    fin = (ahora_utc() + timedelta(hours=1)).astimezone(ZONA_ARGENTINA)
    with fabrica_sesiones() as s:
        ana = s.scalar(select(Usuario).where(Usuario.email == ANA))
        aula_id = s.scalar(select(Aula.id).where(Aula.nombre == "214"))
        reserva = reservas.crear_reserva(s, ana, aula_id, hora_fin=f"{fin:%H:%M}")
        codigo, uid = reserva.codigo, reserva.llave.rfid_uid
        s.commit()
    datos = json.dumps({"eventId": "equipo-01-us16-1", "codigo": codigo, "uid": uid, "slot": 1}).encode()
    with fabrica_sesiones() as s:
        assert protocolo.procesar_evento(s, "equipo-01", "retiro_confirmado", datos)["ok"] is True
    with fabrica_sesiones() as s:
        assert s.scalar(select(Prestamo.hora_fin)) is not None
