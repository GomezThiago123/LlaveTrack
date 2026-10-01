"""Tests de las reglas de reserva (US-03)."""

import threading
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.errores import ErrorNegocio
from app.modelos import Aula, EstadoLlave, EstadoReserva, Llave, Reserva, Usuario
from app.servicios import reservas
from app.tipos import ahora_utc

ANA = "ana.perez@example.com"
BRUNO = "bruno.gomez@example.com"


def usuario(sesion, email) -> Usuario:
    return sesion.scalar(select(Usuario).where(Usuario.email == email))


def aula(sesion, nombre) -> Aula:
    return sesion.scalar(select(Aula).where(Aula.nombre == nombre))


def estado_llave(sesion, nombre_aula) -> EstadoLlave:
    sesion.expire_all()  # releer de la base, no de la memoria de la sesion
    return sesion.scalar(select(Llave.estado).join(Aula).where(Aula.nombre == nombre_aula))


def test_reservar_devuelve_codigo_y_reserva_la_llave(sesion):
    reserva = reservas.crear_reserva(sesion, usuario(sesion, ANA), aula(sesion, "214").id)
    sesion.commit()

    assert len(reserva.codigo) == 6 and reserva.codigo.isdigit()
    minutos = (reserva.expira_en - reserva.creada_en) / timedelta(minutes=1)
    assert minutos == 10
    assert reserva.estado == EstadoReserva.PENDIENTE
    assert estado_llave(sesion, "214") == EstadoLlave.RESERVADA


def test_llave_ya_reservada_no_se_puede_reservar(sesion):
    reservas.crear_reserva(sesion, usuario(sesion, ANA), aula(sesion, "214").id)
    with pytest.raises(ErrorNegocio) as error:
        reservas.crear_reserva(sesion, usuario(sesion, BRUNO), aula(sesion, "214").id)
    assert error.value.codigo == "LLAVE_NO_DISPONIBLE"


def test_dos_pedidos_simultaneos_por_la_misma_llave_solo_gana_uno(fabrica_sesiones):
    """Regla obligatoria del CLAUDE.md: una llave nunca puede quedar tomada dos veces."""
    with fabrica_sesiones() as s:
        aula_id = aula(s, "214").id

    largada = threading.Barrier(2)  # para que los dos hilos arranquen a la vez
    resultados = []

    def pedir(email):
        with fabrica_sesiones() as s:
            largada.wait()
            try:
                reservas.crear_reserva(s, usuario(s, email), aula_id)
                s.commit()
                resultados.append("ok")
            except ErrorNegocio as e:
                resultados.append(e.codigo)

    hilos = [threading.Thread(target=pedir, args=(email,)) for email in (ANA, BRUNO)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert sorted(resultados) == ["LLAVE_NO_DISPONIBLE", "ok"]
    with fabrica_sesiones() as s:
        assert len(s.scalars(select(Reserva)).all()) == 1
        assert estado_llave(s, "214") == EstadoLlave.RESERVADA


def test_un_docente_tiene_como_maximo_una_reserva_pendiente(sesion):
    ana = usuario(sesion, ANA)
    reservas.crear_reserva(sesion, ana, aula(sesion, "214").id)
    with pytest.raises(ErrorNegocio) as error:
        reservas.crear_reserva(sesion, ana, aula(sesion, "215").id)
    assert error.value.codigo == "YA_TIENE_RESERVA"
    assert estado_llave(sesion, "215") == EstadoLlave.DISPONIBLE


def test_reserva_vencida_libera_la_llave(sesion):
    hace_11_min = ahora_utc() - timedelta(minutes=11)
    reserva = reservas.crear_reserva(
        sesion, usuario(sesion, ANA), aula(sesion, "214").id, ahora=hace_11_min
    )
    sesion.commit()

    assert reservas.vencer_reservas(sesion) == 1
    sesion.commit()

    sesion.refresh(reserva)
    assert reserva.estado == EstadoReserva.VENCIDA
    assert estado_llave(sesion, "214") == EstadoLlave.DISPONIBLE
    assert reservas.reserva_activa(sesion, usuario(sesion, ANA)) is None
    # Y otro docente ya la puede pedir
    reservas.crear_reserva(sesion, usuario(sesion, BRUNO), aula(sesion, "214").id)


def test_cancelar_libera_la_llave(sesion):
    ana = usuario(sesion, ANA)
    reserva = reservas.crear_reserva(sesion, ana, aula(sesion, "214").id)
    reservas.cancelar_reserva(sesion, ana, reserva.id)

    assert reserva.estado == EstadoReserva.CANCELADA
    assert estado_llave(sesion, "214") == EstadoLlave.DISPONIBLE
    with pytest.raises(ErrorNegocio) as error:
        reservas.cancelar_reserva(sesion, ana, reserva.id)
    assert error.value.codigo == "RESERVA_NO_PENDIENTE"


def test_no_se_puede_cancelar_la_reserva_de_otro(sesion):
    reserva = reservas.crear_reserva(sesion, usuario(sesion, ANA), aula(sesion, "214").id)
    with pytest.raises(ErrorNegocio) as error:
        reservas.cancelar_reserva(sesion, usuario(sesion, BRUNO), reserva.id)
    assert error.value.codigo == "RESERVA_NO_ENCONTRADA"


def test_codigo_no_repite_el_de_otra_reserva_pendiente(sesion, monkeypatch):
    # El generador "saca" 123456 dos veces seguidas y despues 654321
    numeros = iter([123456, 123456, 654321])
    monkeypatch.setattr(reservas.secrets, "randbelow", lambda _: next(numeros))

    r1 = reservas.crear_reserva(sesion, usuario(sesion, ANA), aula(sesion, "214").id)
    r2 = reservas.crear_reserva(sesion, usuario(sesion, BRUNO), aula(sesion, "215").id)
    assert (r1.codigo, r2.codigo) == ("123456", "654321")


def test_aula_inexistente(sesion):
    with pytest.raises(ErrorNegocio) as error:
        reservas.crear_reserva(sesion, usuario(sesion, ANA), 9999)
    assert error.value.codigo == "AULA_NO_ENCONTRADA"


# --- A traves de la API HTTP ---


def id_aula(fabrica_sesiones, nombre) -> int:
    # Abre y cierra su propia sesion: una sesion abierta bloquearia a la API (ver app/db.py)
    with fabrica_sesiones() as s:
        return aula(s, nombre).id


def test_api_ciclo_reservar_consultar_cancelar(cliente, fabrica_sesiones):
    ana = {"X-Usuario-Email": ANA}
    aula_id = id_aula(fabrica_sesiones, "214")

    res = cliente.post("/api/reservas", json={"aulaId": aula_id}, headers=ana)
    assert res.status_code == 201
    reserva = res.json()
    assert set(reserva) == {"id", "aula", "codigo", "expiraEn", "estado"}
    assert reserva["aula"] == "214"

    activa = cliente.get("/api/reservas/activa", headers=ana)
    assert activa.json()["codigo"] == reserva["codigo"]

    assert cliente.delete(f"/api/reservas/{reserva['id']}", headers=ana).status_code == 204
    assert cliente.get("/api/reservas/activa", headers=ana).json() is None


def test_api_sin_usuario_responde_401_con_formato_de_error(cliente):
    res = cliente.post("/api/reservas", json={"aulaId": 1})
    assert res.status_code == 401
    assert res.json()["error"]["codigo"] == "NO_AUTENTICADO"


def test_api_error_de_negocio_tiene_codigo_y_mensaje(cliente, fabrica_sesiones):
    aula_id = id_aula(fabrica_sesiones, "214")
    cliente.post("/api/reservas", json={"aulaId": aula_id}, headers={"X-Usuario-Email": ANA})
    res = cliente.post("/api/reservas", json={"aulaId": aula_id}, headers={"X-Usuario-Email": BRUNO})
    assert res.status_code == 409
    assert res.json() == {
        "error": {"codigo": "LLAVE_NO_DISPONIBLE", "mensaje": "La llave del aula 214 no está disponible."}
    }


def test_api_datos_invalidos(cliente):
    res = cliente.post("/api/reservas", json={"aula": "214"}, headers={"X-Usuario-Email": ANA})
    assert res.status_code == 422
    assert res.json()["error"]["codigo"] == "DATOS_INVALIDOS"
