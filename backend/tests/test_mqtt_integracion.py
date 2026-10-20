"""Test de punta a punta con el broker MQTT real (Mosquitto en localhost:1883).

Se saltea si el broker no esta. Usa un prefijo de topicos propio y unico, asi no
interfiere con un servidor de desarrollo que este corriendo al mismo tiempo.
"""

import json
import queue
import secrets
import socket
import time

import paho.mqtt.client as mqtt
import pytest
from sqlalchemy import select

from app.modelos import Aula, Usuario
from app.mqtt_cliente import ClienteMqtt
from app.servicios import conexion, reservas


def broker_disponible() -> bool:
    try:
        socket.create_connection(("localhost", 1883), timeout=1).close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not broker_disponible(), reason="Mosquitto no esta corriendo en localhost:1883")


def test_retiro_por_mqtt_de_punta_a_punta(fabrica_sesiones):
    # Se reserva antes de conectar el servidor: al conectarse marca los equipos offline
    # hasta recibir su `estado` (US-20), y este test no publica `estado`
    with fabrica_sesiones() as s:
        ana = s.scalar(select(Usuario).where(Usuario.email == "ana.perez@example.com"))
        aula_id = s.scalar(select(Aula.id).where(Aula.nombre == "214"))
        codigo = reservas.crear_reserva(s, ana, aula_id).codigo
        s.commit()

    prefijo = f"llavetrack-test-{secrets.token_hex(4)}/v1"
    servidor = ClienteMqtt(fabrica_sesiones, client_id=f"test-servidor-{secrets.token_hex(4)}", prefijo=prefijo)
    servidor.iniciar("localhost", 1883)

    respuestas: queue.Queue = queue.Queue()
    conectado: queue.Queue = queue.Queue()
    equipo = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"test-equipo-{secrets.token_hex(4)}")
    equipo.on_message = lambda _c, _u, msg: respuestas.put(json.loads(msg.payload))
    equipo.on_subscribe = lambda *_args: conectado.put(True)
    equipo.connect("localhost", 1883)
    equipo.loop_start()
    try:
        equipo.subscribe(f"{prefijo}/equipo-01/resp", qos=1)
        conectado.get(timeout=5)

        # Reintenta hasta que el servidor este suscrito (como hace el equipo real)
        mensaje = json.dumps({"eventId": "equipo-01-test-0001", "codigo": codigo})
        respuesta = None
        for _ in range(10):
            equipo.publish(f"{prefijo}/equipo-01/evt/solicitud_retiro", mensaje)
            try:
                respuesta = respuestas.get(timeout=1)
                break
            except queue.Empty:
                continue

        assert respuesta is not None, "el servidor no respondio por MQTT"
        assert respuesta["eventId"] == "equipo-01-test-0001"
        assert respuesta["ok"] is True and respuesta["aula"] == "214"
    finally:
        equipo.disconnect()
        equipo.loop_stop()
        servidor.detener()


# --- US-20: el servidor sabe si el equipo esta conectado ---


def esperar(condicion, segundos: float) -> bool:
    """Revisa la condicion cada 0,2 s hasta que se cumpla o pase el tiempo."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.2)
    return condicion()


def equipo_online(fabrica_sesiones) -> bool:
    with fabrica_sesiones() as s:
        return conexion.equipo_online(s)


def test_lwt_y_estado_retenido(fabrica_sesiones):
    """El equipo se conecta (estado retenido online), el servidor arranca despues y lo recupera.
    Despues el equipo se "desenchufa" sin despedirse y el broker publica su LWT."""
    prefijo = f"llavetrack-test-{secrets.token_hex(4)}/v1"
    topico_estado = f"{prefijo}/equipo-01/estado"

    with fabrica_sesiones() as s:  # parte de offline, como despues de un reinicio
        conexion.marcar_equipos_offline(s)
        s.commit()

    equipo = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"test-equipo-{secrets.token_hex(4)}")
    equipo.will_set(topico_estado, json.dumps({"online": False}), qos=1, retain=True)
    equipo.connect("localhost", 1883, keepalive=1)  # keepalive corto: el LWT llega en ~1,5 s
    equipo.loop_start()
    equipo.publish(topico_estado, json.dumps({"online": True}), qos=1, retain=True).wait_for_publish(5)

    servidor = ClienteMqtt(fabrica_sesiones, client_id=f"test-servidor-{secrets.token_hex(4)}", prefijo=prefijo)
    servidor.iniciar("localhost", 1883)
    try:
        # Reinicio del servidor: recupera el estado del mensaje retenido
        assert esperar(lambda: equipo_online(fabrica_sesiones), 5)

        # Corte de luz: deja de mandar pings sin desconectarse. El broker publica el LWT
        equipo.loop_stop()
        assert esperar(lambda: not equipo_online(fabrica_sesiones), 6)
    finally:
        equipo.disconnect()
        servidor.detener()
        # Limpia el mensaje retenido de prueba
        limpieza = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        limpieza.connect("localhost", 1883)
        limpieza.loop_start()
        limpieza.publish(topico_estado, b"", retain=True).wait_for_publish(5)
        limpieza.disconnect()
        limpieza.loop_stop()
