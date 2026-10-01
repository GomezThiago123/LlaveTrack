"""Simulador del equipo LlaveTrack: se hace pasar por el ESP32 via MQTT.

Publica los mismos eventos que el equipo real (docs/protocolo-mqtt.md) y muestra
lo que haria el LCD con cada respuesta. Sirve para probar todo sin hardware.

Uso (desde backend/, con el .venv activado):
    python simulador/simulador.py inicio
    python simulador/simulador.py retirar 482913
    python simulador/simulador.py timeout 482913
    python simulador/simulador.py devolver 04A1B2C3
    python simulador/simulador.py offline
Opciones: --equipo equipo-01  --host localhost  --puerto 1883  --repetir
"""

import argparse
import json
import queue
import secrets
import sys
from pathlib import Path

import paho.mqtt.client as mqtt

PREFIJO = "llavetrack/v1"
ESPERA_RESPUESTA = 5  # segundos, igual que el equipo real
REINTENTOS = 3
# Como el ESP32, el simulador recuerda en que slot quedo el disco (el slot vacio de la ventana)
ARCHIVO_ESTADO = Path(__file__).parent / ".estado.json"


class Equipo:
    def __init__(self, device_id: str, host: str, puerto: int, repetir: bool):
        self.device_id = device_id
        self.repetir = repetir
        # eventId unico aunque el equipo se reinicie: random de arranque + contador
        self.arranque = secrets.token_hex(2)
        self.contador = 0
        self.respuestas: queue.Queue = queue.Queue()

        self.cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-{device_id}")
        # LWT: si el simulador se corta sin despedirse, el broker avisa que quedo offline
        self.cliente.will_set(self.topico("estado"), json.dumps({"online": False}), qos=1, retain=True)
        self.cliente.on_message = lambda _c, _u, msg: self.respuestas.put(json.loads(msg.payload))
        try:
            self.cliente.connect(host, puerto)
        except OSError as error:
            sys.exit(f"No se pudo conectar al broker MQTT en {host}:{puerto} ({error}). ¿Está Mosquitto?")
        self.cliente.subscribe(self.topico("resp"), qos=1)
        self.cliente.loop_start()

    def topico(self, sufijo: str) -> str:
        return f"{PREFIJO}/{self.device_id}/{sufijo}"

    def cerrar(self) -> None:
        self.cliente.disconnect()
        self.cliente.loop_stop()

    def publicar_estado(self, online: bool) -> None:
        self.cliente.publish(self.topico("estado"), json.dumps({"online": online}), qos=1, retain=True).wait_for_publish()

    def evento(self, tipo: str, **datos) -> dict | None:
        """Publica un evento y espera la respuesta con su eventId. Reintenta como el ESP32."""
        self.contador += 1
        event_id = f"{self.device_id}-{self.arranque}-{self.contador:04d}"
        mensaje = json.dumps({"eventId": event_id, **datos})
        envios = 2 if self.repetir else 1

        for intento in range(1, REINTENTOS + 1):
            for _ in range(envios):
                print(f"  → evt/{tipo} {mensaje}")
                self.cliente.publish(self.topico(f"evt/{tipo}"), mensaje)
            respuesta = self._esperar(event_id)
            if respuesta is not None:
                if self.repetir:  # la respuesta al duplicado tiene que ser igual a la primera
                    self._esperar(event_id, "resp (duplicado)")
                return respuesta
            print(f"  LCD: Sin respuesta (intento {intento}/{REINTENTOS}), reintentando...")
        print("  LCD: Sin conexion")
        return None

    def _esperar(self, event_id: str, etiqueta: str = "resp") -> dict | None:
        try:
            while True:
                respuesta = self.respuestas.get(timeout=ESPERA_RESPUESTA)
                if respuesta.get("eventId") == event_id:  # ignora respuestas viejas o ajenas
                    print(f"  ← {etiqueta} {json.dumps(respuesta)}")
                    return respuesta
        except queue.Empty:
            return None


def leer_slot_reposo() -> int | None:
    try:
        return json.loads(ARCHIVO_ESTADO.read_text())["slotReposo"]
    except (OSError, ValueError, KeyError):
        return None


def guardar_slot_reposo(slot: int | None) -> None:
    ARCHIVO_ESTADO.write_text(json.dumps({"slotReposo": slot}))


def lcd(linea1: str, linea2: str = "") -> None:
    # El LCD real tiene 16 caracteres por linea
    print(f"  LCD: [{linea1[:16]:<16}]\n       [{linea2[:16]:<16}]")


# --- Comandos ---


def cmd_inicio(eq: Equipo, args) -> None:
    eq.publicar_estado(True)
    res = eq.evento("inicio", slotsTotales=args.slots, slotsReservados=[0])
    if res and res["ok"]:
        guardar_slot_reposo(res["slotReposo"])
        print(f"  Disco: gira al slot {res['slotReposo']} (vacio, frente a la ventana)")
        lcd("LlaveTrack", "A:Retirar B:Dev.")


def _pedir_llave(eq: Equipo, codigo: str) -> dict | None:
    lcd("Codigo:", codigo)
    res = eq.evento("solicitud_retiro", codigo=codigo)
    if res is None:
        return None
    if not res["ok"]:
        lcd("Codigo rechazado", res["motivo"].replace("_", " ").lower())
        return None
    print(f"  Disco: gira al slot {res['slot']} y verifica que lee el UID {res['uid']}")
    lcd(f"Aula {res['aula']}", "Retire la llave")
    return res


def cmd_retirar(eq: Equipo, args) -> None:
    res = _pedir_llave(eq, args.codigo)
    if res is None:
        return
    print("  (el docente saca la llave: el UID deja de leerse)")
    confirmado = eq.evento("retiro_confirmado", codigo=args.codigo, uid=res["uid"], slot=res["slot"])
    if confirmado and confirmado["ok"]:
        guardar_slot_reposo(res["slot"])  # el slot que quedo vacio queda frente a la ventana
        lcd("Hasta luego", res["apellido"])


def cmd_timeout(eq: Equipo, args) -> None:
    res = _pedir_llave(eq, args.codigo)
    if res is None:
        return
    print("  (pasan 60 s y nadie retira la llave)")
    eq.evento("retiro_timeout", codigo=args.codigo)
    print(f"  Disco: vuelve al slot {leer_slot_reposo()} (vacio)")
    lcd("Tiempo agotado", "La reserva sigue")


def cmd_devolver(eq: Equipo, args) -> None:
    slot = args.slot if args.slot is not None else leer_slot_reposo()
    if slot is None:
        sys.exit("No sé en qué slot está la ventana: corré primero 'inicio' o usá --slot N")
    lcd("Cuelgue la", "llave")
    print(f"  (el docente cuelga la llave {args.uid} en el slot {slot})")
    res = eq.evento("devolucion", uid=args.uid, slot=slot)
    if res is None:
        return
    if not res["ok"]:
        lcd("Llave no", "reconocida")
        return
    guardar_slot_reposo(res["slotReposo"])
    lcd(f"Aula {res['aula']}", f"Gracias {res['apellido']}")
    print(f"  Disco: gira al slot {res['slotReposo']} (vacio)")


def cmd_offline(eq: Equipo, _args) -> None:
    eq.publicar_estado(False)
    print("  Equipo marcado OFFLINE (como si se hubiera desconectado)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador del equipo LlaveTrack (ESP32) via MQTT")
    parser.add_argument("--equipo", default="equipo-01", help="deviceId (default: equipo-01)")
    parser.add_argument("--host", default="localhost", help="broker MQTT (default: localhost)")
    parser.add_argument("--puerto", type=int, default=1883)
    parser.add_argument("--repetir", action="store_true", help="manda cada evento dos veces (prueba de duplicados)")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("inicio", help="el equipo arranca: se conecta y pide el slot de reposo")
    p.add_argument("--slots", type=int, default=24, help="slots totales del disco (default: 24)")
    p.set_defaults(funcion=cmd_inicio)
    p = sub.add_parser("retirar", help="ingresa un codigo y retira la llave")
    p.add_argument("codigo")
    p.set_defaults(funcion=cmd_retirar)
    p = sub.add_parser("timeout", help="ingresa un codigo pero nadie retira la llave")
    p.add_argument("codigo")
    p.set_defaults(funcion=cmd_timeout)
    p = sub.add_parser("devolver", help="cuelga la llave con ese UID en el slot de la ventana")
    p.add_argument("uid")
    p.add_argument("--slot", type=int, help="slot donde se cuelga (default: el de reposo)")
    p.set_defaults(funcion=cmd_devolver)
    p = sub.add_parser("offline", help="marca el equipo como desconectado")
    p.set_defaults(funcion=cmd_offline)

    args = parser.parse_args()
    eq = Equipo(args.equipo, args.host, args.puerto, args.repetir)
    try:
        args.funcion(eq, args)
    finally:
        eq.cerrar()


if __name__ == "__main__":
    main()
