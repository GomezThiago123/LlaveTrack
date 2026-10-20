"""Conexion del servidor con el broker MQTT (Mosquitto).

paho-mqtt corre en su propio hilo: recibe los mensajes del equipo, los pasa a
app/protocolo.py (una sesion de base por mensaje) y publica la respuesta.
Si el broker no esta, el servidor arranca igual y paho reintenta conectarse solo.

Tambien publica la lista de aulas faltantes de cada equipo (US-23), retenida: el equipo
la recibe sola al conectarse, sin pedirla. Y su propio estado en `servidor/estado` (US-24),
con LWT: si el servidor se cae, el broker avisa a los equipos y apagan el LED de conexion.
"""

import json
import logging

import paho.mqtt.client as mqtt
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app import protocolo
from app.config import config
from app.modelos import Dispositivo
from app.servicios import conexion, equipo

log = logging.getLogger(__name__)

PREFIJO = "llavetrack/v1"
# deviceId reservado: `{prefijo}/servidor/estado` es el estado del servidor, no de un equipo
SERVIDOR = "servidor"


class ClienteMqtt:
    def __init__(
        self,
        fabrica_sesiones: sessionmaker,
        client_id: str = "llavetrack-servidor",
        prefijo: str = PREFIJO,  # los tests usan otro, para no cruzarse con un servidor en marcha
        keepalive: int = 15,  # si el servidor se cae, el broker publica su LWT en ~1,5 x keepalive
    ):
        self.fabrica_sesiones = fabrica_sesiones
        self.prefijo = prefijo
        self.keepalive = keepalive
        self.topico_estado = f"{prefijo}/{SERVIDOR}/estado"
        self.cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        # LWT (US-24): si el servidor se corta sin despedirse, el broker publica que quedo offline
        self.cliente.will_set(self.topico_estado, json.dumps({"online": False}), qos=1, retain=True)
        if config.mqtt_usuario:
            self.cliente.username_pw_set(config.mqtt_usuario, config.mqtt_clave)
        self.cliente.reconnect_delay_set(min_delay=1, max_delay=30)
        self.cliente.on_connect = self._al_conectar
        self.cliente.on_disconnect = self._al_desconectar
        self.cliente.on_message = self._al_recibir
        # Ultima lista de faltantes publicada por equipo, para publicar solo cuando cambia
        self.faltantes_publicados: dict[str, list[str]] = {}

    def iniciar(self, host: str = config.mqtt_host, puerto: int = config.mqtt_puerto) -> None:
        # El keepalive sirve para los dos lados: paho nota si se cae el broker, y el broker
        # nota si se cae el servidor (y publica su LWT)
        self.cliente.connect_async(host, puerto, keepalive=self.keepalive)
        self.cliente.loop_start()  # arranca el hilo de paho

    def detener(self) -> None:
        # Apagado prolijo: el LWT solo se publica si se corta, asi que avisa a mano
        if self.cliente.is_connected():
            self.cliente.publish(self.topico_estado, json.dumps({"online": False}), qos=1, retain=True).wait_for_publish(5)
        self.cliente.disconnect()
        self.cliente.loop_stop()

    def _al_conectar(self, cliente, _userdata, _flags, codigo, _props):
        if codigo.is_failure:
            log.error("No se pudo conectar al broker MQTT: %s", codigo)
            return
        log.info("Conectado al broker MQTT")
        cliente.publish(self.topico_estado, json.dumps({"online": True}), qos=1, retain=True)
        # Mientras estuvo desconectado no supo nada de los equipos: los marca offline y al
        # suscribirse a `estado` el broker le manda el ultimo mensaje retenido de cada uno.
        # Asi tambien recupera el estado real cuando se reinicia el servidor.
        self._marcar_equipos_offline()
        # Se suscribe en cada conexion (tambien al reconectar). "+" = cualquier equipo / evento
        cliente.subscribe(f"{self.prefijo}/+/evt/+", qos=1)
        cliente.subscribe(f"{self.prefijo}/+/estado", qos=1)
        cliente.subscribe(f"{self.prefijo}/+/latido", qos=0)
        # Por si algo cambio mientras estuvo desconectado: republica los faltantes de todos
        self.faltantes_publicados.clear()
        self._publicar_faltantes()

    def _al_desconectar(self, _cliente, _userdata, _flags, codigo, _props):
        log.warning("Desconectado del broker MQTT (%s). Reintentando...", codigo)
        # Sin broker no se puede saber si el equipo sigue vivo: se lo trata como desconectado
        self._marcar_equipos_offline()

    def _marcar_equipos_offline(self) -> None:
        try:
            with self.fabrica_sesiones() as sesion:
                conexion.marcar_equipos_offline(sesion)
                sesion.commit()
        except Exception:
            log.exception("No se pudieron marcar los equipos offline")

    def _publicar_faltantes(self, device_id: str | None = None) -> None:
        """Publica `faltantes` (retenido) del equipo indicado, o de todos, si cambio."""
        try:
            with self.fabrica_sesiones() as sesion:
                aulas = equipo.aulas_faltantes(sesion)
                consulta = select(Dispositivo.device_id)
                if device_id:  # solo si es un equipo conocido
                    consulta = consulta.where(Dispositivo.device_id == device_id)
                equipos = list(sesion.scalars(consulta))
        except Exception:
            log.exception("No se pudieron calcular las aulas faltantes")
            return
        for d in equipos:
            if self.faltantes_publicados.get(d) == aulas:
                continue
            self.cliente.publish(f"{self.prefijo}/{d}/faltantes", json.dumps({"aulas": aulas}), qos=1, retain=True)
            self.faltantes_publicados[d] = aulas

    def _al_recibir(self, cliente, _userdata, mensaje: mqtt.MQTTMessage):
        # Topico: {prefijo}/{deviceId}/evt/{tipo}, {prefijo}/{deviceId}/estado o {prefijo}/{deviceId}/latido
        partes = mensaje.topic.removeprefix(self.prefijo + "/").split("/")
        device_id = partes[0]
        if device_id == SERVIDOR:  # su propio estado: coincide con el patron "+/estado" de los equipos
            return
        try:
            with self.fabrica_sesiones() as sesion:
                if partes[1] == "estado":
                    protocolo.procesar_estado(sesion, device_id, mensaje.payload)
                    return
                if partes[1] == "latido":
                    protocolo.procesar_latido(sesion, device_id)
                    return
                respuesta = protocolo.procesar_evento(sesion, device_id, partes[2], mensaje.payload)
            if respuesta is not None:
                cliente.publish(f"{self.prefijo}/{device_id}/resp", json.dumps(respuesta), qos=1)
            if partes[2] == "inicio":
                self.faltantes_publicados.pop(device_id, None)  # el equipo arranco: se la manda igual
            # Solo un retiro o una devolucion cambian la lista; se publica si cambio
            self._publicar_faltantes(device_id)
        except Exception:
            # Un error con un mensaje no puede tirar abajo el hilo de MQTT
            log.exception("Error procesando %s", mensaje.topic)
