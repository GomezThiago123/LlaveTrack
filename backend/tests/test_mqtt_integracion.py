"""Test de punta a punta con el broker MQTT real (Mosquitto en localhost:1883).

Se saltea si el broker no esta. Usa un prefijo de topicos propio y unico, asi no
interfiere con un servidor de desarrollo que este corriendo al mismo tiempo.
"""

import json
import queue
import secrets
import socket

import paho.mqtt.client as mqtt
import pytest
from sqlalchemy import select

from app.modelos import Aula, Usuario
from app.mqtt_cliente import ClienteMqtt
from app.servicios import reservas


def broker_disponible() -> bool:
    try:
        socket.create_connection(("localhost", 1883), timeout=1).close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not broker_disponible(), reason="Mosquitto no esta corriendo en localhost:1883")


def test_retiro_por_mqtt_de_punta_a_punta(fabrica_sesiones):
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

        with fabrica_sesiones() as s:
            ana = s.scalar(select(Usuario).where(Usuario.email == "ana.perez@example.com"))
            aula_id = s.scalar(select(Aula.id).where(Aula.nombre == "214"))
            codigo = reservas.crear_reserva(s, ana, aula_id).codigo
            s.commit()

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
