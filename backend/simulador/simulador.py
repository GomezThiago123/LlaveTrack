"""Simulador del equipo LlaveTrack: se hace pasar por el ESP32 via MQTT.

Publica los mismos mensajes que el equipo real (docs/protocolo-mqtt.md) y muestra
lo que haria el LCD con cada respuesta. Sirve para probar todo sin hardware.

Como el equipo real, queda prendido hasta que lo apagues: al arrancar se conecta
(con LWT), manda `inicio` y despues un latido cada 30 s. Los comandos se escriben
en el prompt.

Uso (desde backend/, con el .venv activado):
    python simulador/simulador.py
    equipo> retirar 482913
    equipo> devolver 04A1B2C3
    equipo> desenchufar
    equipo> salir
Opciones: --equipo equipo-01  --host localhost  --puerto 1883  --slots 24  --repetir
"""

import argparse
import json
import queue
import secrets
import shlex
import sys
import threading

import paho.mqtt.client as mqtt

PREFIJO = "llavetrack/v1"
ESPERA_RESPUESTA = 5  # segundos, igual que el equipo real
REINTENTOS = 3
# Iguales a los del firmware (config.h): con keepalive de 10 s el broker publica el LWT
# unos 15 s despues de que el equipo se corta (1,5 x keepalive)
KEEPALIVE = 10
LATIDO_SEGUNDOS = 30

AYUDA = """Comandos:
  retirar CODIGO       ingresa el codigo en el teclado y retira la llave
  timeout CODIGO       ingresa el codigo pero nadie retira la llave
  devolver UID [SLOT]  cuelga la llave con ese UID (por defecto, en el slot de la ventana)
  desenchufar          corte de luz: se calla sin despedirse (el broker publica el LWT en ~15 s)
  enchufar             vuelve a arrancar despues de desenchufar
  salir                se apaga prolijo (avisa que queda offline)"""


def lcd(linea1: str, linea2: str = "") -> None:
    # El LCD real tiene 16 caracteres por linea
    print(f"  LCD: [{linea1[:16]:<16}]\n       [{linea2[:16]:<16}]")


class Equipo:
    def __init__(self, args):
        self.device_id = args.equipo
        self.host, self.puerto = args.host, args.puerto
        self.slots = args.slots
        self.repetir = args.repetir
        # eventId unico aunque el equipo se reinicie: random de arranque + contador
        self.arranque = secrets.token_hex(2)
        self.contador = 0
        self.respuestas: queue.Queue = queue.Queue()
        self.slot_reposo: int | None = None  # slot vacio frente a la ventana
        self.enchufado = False
        self.parar_latido = threading.Event()

        self.cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-{self.device_id}")
        # LWT: si el equipo se corta sin despedirse, el broker publica que quedo offline
        self.cliente.will_set(self.topico("estado"), json.dumps({"online": False}), qos=1, retain=True)
        self.cliente.on_message = lambda _c, _u, msg: self.respuestas.put(json.loads(msg.payload))

    def topico(self, sufijo: str) -> str:
        return f"{PREFIJO}/{self.device_id}/{sufijo}"

    # --- Conexion ---

    def enchufar(self) -> None:
        """Arranca como el ESP32: conecta, avisa que esta online, manda `inicio` y empieza a latir."""
        try:
            if self.contador == 0:
                self.cliente.connect(self.host, self.puerto, keepalive=KEEPALIVE)
            else:
                self.cliente.reconnect()
        except OSError as error:
            sys.exit(f"No se pudo conectar al broker MQTT en {self.host}:{self.puerto} ({error}). ¿Está Mosquitto?")
        self.cliente.loop_start()
        self.cliente.subscribe(self.topico("resp"), qos=1)
        self.publicar_estado(True)
        self.enchufado = True

        res = self.evento("inicio", slotsTotales=self.slots, slotsReservados=[0])
        if res and res["ok"]:
            self.slot_reposo = res["slotReposo"]
            print(f"  Disco: homing y gira al slot {self.slot_reposo} (vacio, frente a la ventana)")
            lcd("LlaveTrack", "A:Retirar B:Dev.")

        self.parar_latido.clear()
        threading.Thread(target=self._latir, daemon=True).start()

    def _latir(self) -> None:
        # wait() devuelve True si se pidio parar; si no, pasaron LATIDO_SEGUNDOS
        while not self.parar_latido.wait(LATIDO_SEGUNDOS):
            self.cliente.publish(self.topico("latido"), "{}")

    def desenchufar(self) -> None:
        """Corte de luz: deja de mandar todo (ni latidos ni pings) sin desconectarse."""
        self.parar_latido.set()
        self.cliente.loop_stop()
        self.enchufado = False
        print(f"  (sin luz) El broker va a publicar el LWT en ~{KEEPALIVE * 3 // 2} s.")
        print("  Mirá la web: en el próximo refresco el equipo aparece desconectado.")

    def apagar(self) -> None:
        """Apagado prolijo: avisa que queda offline (el LWT solo se publica si se corta)."""
        self.parar_latido.set()
        if self.enchufado:
            self.publicar_estado(False)
            self.cliente.disconnect()
            self.cliente.loop_stop()

    def publicar_estado(self, online: bool) -> None:
        self.cliente.publish(self.topico("estado"), json.dumps({"online": online}), qos=1, retain=True).wait_for_publish(5)

    # --- Eventos ---

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
        lcd("Sin conexion")
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

    # --- Lo que hace el docente en el equipo ---

    def _pedir_llave(self, codigo: str) -> dict | None:
        lcd("Codigo:", codigo)
        res = self.evento("solicitud_retiro", codigo=codigo)
        if res is None:
            return None
        if not res["ok"]:
            lcd("Codigo rechazado", res["motivo"].replace("_", " ").lower())
            return None
        print(f"  Disco: gira al slot {res['slot']} y verifica que lee el UID {res['uid']}")
        lcd(f"Aula {res['aula']}", "Retire la llave")
        return res

    def retirar(self, codigo: str) -> None:
        res = self._pedir_llave(codigo)
        if res is None:
            return
        print("  (el docente saca la llave: el UID deja de leerse)")
        confirmado = self.evento("retiro_confirmado", codigo=codigo, uid=res["uid"], slot=res["slot"])
        if confirmado and confirmado["ok"]:
            self.slot_reposo = res["slot"]  # el slot que quedo vacio queda frente a la ventana
            lcd("Hasta luego", res["apellido"])

    def timeout(self, codigo: str) -> None:
        if self._pedir_llave(codigo) is None:
            return
        print("  (pasan 60 s y nadie retira la llave)")
        self.evento("retiro_timeout", codigo=codigo)
        print(f"  Disco: vuelve al slot {self.slot_reposo} (vacio)")
        lcd("Tiempo agotado", "La reserva sigue")

    def devolver(self, uid: str, slot: int | None) -> None:
        slot = self.slot_reposo if slot is None else slot
        if slot is None:
            print("  No sé en qué slot está la ventana: indicalo, ej. devolver 04A1B2C3 5")
            return
        lcd("Cuelgue la", "llave")
        print(f"  (el docente cuelga la llave {uid} en el slot {slot})")
        res = self.evento("devolucion", uid=uid, slot=slot)
        if res is None:
            return
        if not res["ok"]:
            lcd("Llave no", "reconocida")
            return
        self.slot_reposo = res["slotReposo"]
        lcd(f"Aula {res['aula']}", f"Gracias {res['apellido']}")
        print(f"  Disco: gira al slot {res['slotReposo']} (vacio)")


def ejecutar(eq: Equipo, linea: str) -> bool:
    """Ejecuta un comando. Devuelve False para salir."""
    try:
        partes = shlex.split(linea)
    except ValueError:
        partes = linea.split()
    if not partes:
        return True
    comando, args = partes[0].lower(), partes[1:]

    if comando in ("salir", "exit", "quit"):
        return False
    if comando in ("ayuda", "help", "?"):
        print(AYUDA)
    elif comando == "enchufar":
        if eq.enchufado:
            print("  Ya está enchufado.")
        else:
            eq.enchufar()
    elif not eq.enchufado:
        # Como el equipo real: sin conexion no entrega ni recibe llaves
        lcd("Sin conexion")
        print("  (está desenchufado: usá 'enchufar')")
    elif comando == "desenchufar":
        eq.desenchufar()
    elif comando in ("retirar", "timeout") and len(args) == 1:
        getattr(eq, comando)(args[0])
    elif comando == "devolver" and len(args) in (1, 2):
        try:
            eq.devolver(args[0], int(args[1]) if len(args) == 2 else None)
        except ValueError:
            print("  El slot tiene que ser un número.")
    else:
        print(f"  No entendí '{linea}'. Escribí 'ayuda' para ver los comandos.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador del equipo LlaveTrack (ESP32) via MQTT")
    parser.add_argument("--equipo", default="equipo-01", help="deviceId (default: equipo-01)")
    parser.add_argument("--host", default="localhost", help="broker MQTT (default: localhost)")
    parser.add_argument("--puerto", type=int, default=1883)
    parser.add_argument("--slots", type=int, default=24, help="slots totales del disco (default: 24)")
    parser.add_argument("--repetir", action="store_true", help="manda cada evento dos veces (prueba de duplicados)")
    args = parser.parse_args()

    eq = Equipo(args)
    print(f"Simulador de {args.equipo}. Escribí 'ayuda' para ver los comandos.")
    eq.enchufar()
    try:
        while True:
            try:
                linea = input("equipo> ")
            except EOFError:  # Ctrl+D, o fin de los comandos si vienen de un archivo
                break
            if not ejecutar(eq, linea):
                break
    except KeyboardInterrupt:  # Ctrl+C
        print()
    finally:
        eq.apagar()
        print("Equipo apagado (offline).")


if __name__ == "__main__":
    main()
