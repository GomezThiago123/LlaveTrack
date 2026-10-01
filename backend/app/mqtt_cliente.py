"""Conexion del servidor con el broker MQTT (Mosquitto).

paho-mqtt corre en su propio hilo: recibe los mensajes del equipo, los pasa a
app/protocolo.py (una sesion de base por mensaje) y publica la respuesta.
Si el broker no esta, el servidor arranca igual y paho reintenta conectarse solo.
"""

import json
import logging

import paho.mqtt.client as mqtt
from sqlalchemy.orm import sessionmaker

from app import protocolo
from app.config import config

log = logging.getLogger(__name__)

PREFIJO = "llavetrack/v1"


class ClienteMqtt:
    def __init__(
        self,
        fabrica_sesiones: sessionmaker,
        client_id: str = "llavetrack-servidor",
        prefijo: str = PREFIJO,  # los tests usan otro, para no cruzarse con un servidor en marcha
    ):
        self.fabrica_sesiones = fabrica_sesiones
        self.prefijo = prefijo
        self.cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if config.mqtt_usuario:
            self.cliente.username_pw_set(config.mqtt_usuario, config.mqtt_clave)
        self.cliente.reconnect_delay_set(min_delay=1, max_delay=30)
        self.cliente.on_connect = self._al_conectar
        self.cliente.on_disconnect = self._al_desconectar
        self.cliente.on_message = self._al_recibir

    def iniciar(self, host: str = config.mqtt_host, puerto: int = config.mqtt_puerto) -> None:
        self.cliente.connect_async(host, puerto)
        self.cliente.loop_start()  # arranca el hilo de paho

    def detener(self) -> None:
        self.cliente.disconnect()
        self.cliente.loop_stop()

    def _al_conectar(self, cliente, _userdata, _flags, codigo, _props):
        if codigo.is_failure:
            log.error("No se pudo conectar al broker MQTT: %s", codigo)
            return
        log.info("Conectado al broker MQTT")
        # Se suscribe en cada conexion (tambien al reconectar). "+" = cualquier equipo / evento
        cliente.subscribe(f"{self.prefijo}/+/evt/+", qos=1)
        cliente.subscribe(f"{self.prefijo}/+/estado", qos=1)

    def _al_desconectar(self, _cliente, _userdata, _flags, codigo, _props):
        log.warning("Desconectado del broker MQTT (%s). Reintentando...", codigo)

    def _al_recibir(self, cliente, _userdata, mensaje: mqtt.MQTTMessage):
        # Topico: {prefijo}/{deviceId}/evt/{tipo}  o  {prefijo}/{deviceId}/estado
        partes = mensaje.topic.removeprefix(self.prefijo + "/").split("/")
        device_id = partes[0]
        try:
            with self.fabrica_sesiones() as sesion:
                if partes[1] == "estado":
                    protocolo.procesar_estado(sesion, device_id, mensaje.payload)
                    return
                respuesta = protocolo.procesar_evento(sesion, device_id, partes[2], mensaje.payload)
            if respuesta is not None:
                cliente.publish(f"{self.prefijo}/{device_id}/resp", json.dumps(respuesta), qos=1)
        except Exception:
            # Un error con un mensaje no puede tirar abajo el hilo de MQTT
            log.exception("Error procesando %s", mensaje.topic)
