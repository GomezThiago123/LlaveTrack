// Firmware del equipo LlaveTrack: la maquina de estados (ver CLAUDE.md, seccion Firmware).
//
// PASO 2a, la red. Al prender:
//   1. homing (busca el tag HOME y mide la vuelta);
//   2. se conecta a la WiFi y al broker (en paralelo, mientras gira);
//   3. manda `inicio` y el disco va al lugar vacio que responde el servidor (slotReposo).
// En reposo, el LCD muestra la hora y las llaves que faltan, y el LED la conexion.
// El retiro (tecla A) y la devolucion (tecla B) son el paso 2b.
//
// Con la tecla D apretada al encender entra al modo diagnostico (diagnostico.cpp, sin red).
// Monitor Serie (115200): "r" estado de la red, "p" donde esta el disco, "h" homing de nuevo.

#include <Arduino.h>
#include <ArduinoJson.h>

#include <vector>

#include "config.h"
#include "diagnostico.h"
#include "disco.h"
#include "lcd.h"
#include "led.h"
#include "motor.h"
#include "protocolo.h"
#include "red.h"
#include "rfid.h"
#include "teclado.h"

namespace {
enum class Estado {
  HOMING,       // buscando el HOME (al prender o con el comando recalibrar)
  IR_A_REPOSO,  // llevando un lugar vacio a la ventana
  REPOSO,
  ERROR,        // el disco no anda: no se entrega nada (el LCD dice por que)
};
Estado estado = Estado::HOMING;
bool modoDiagnostico = false;
bool lectorOk = false;

// `inicio` se manda despues de cada homing y en cada reconexion al broker
bool inicioPendiente = false;
unsigned ultimaConexion = 0;      // redConexiones() la ultima vez que se miro
bool irAlReposoTrasInicio = false;  // despues del homing: el disco quedo en el HOME
int slotReposo = -1;              // el lugar vacio frente a la ventana (-1: no se sabe)

// Falla para avisarle al servidor (crea un incidente que ve el preceptor, US-05)
String errorParaMandar, detalleError;

const char *nombre(Estado e) {
  switch (e) {
    case Estado::HOMING: return "HOMING";
    case Estado::IR_A_REPOSO: return "IR_A_REPOSO";
    case Estado::REPOSO: return "REPOSO";
    case Estado::ERROR: return "ERROR";
  }
  return "?";
}

void cambiarEstado(Estado nuevo) {
  if (nuevo != estado) Serial.printf("[estado] %s -> %s\n", nombre(estado), nombre(nuevo));
  estado = nuevo;
}

void empezarHoming() {
  lcdMensaje("Buscando HOME", "Espere...");
  discoHoming();
  cambiarEstado(Estado::HOMING);
}

void fallar(const char *linea1, const char *linea2, const char *error, const String &detalle) {
  Serial.printf("[estado] ERROR %s: %s\n", error, detalle.c_str());
  lcdMensaje(linea1, linea2);
  errorParaMandar = error;
  detalleError = detalle;
  cambiarEstado(Estado::ERROR);
}

// Las pantallas que rota la linea 1 del LCD en reposo (US-23): la hora y despues
// "Faltan: 105 114" con todas las aulas que entren. Misma regla que pantallas_reposo() del
// simulador (backend/simulador/simulador.py), que tiene tests.
std::vector<String> pantallasReposo(const String &hora, const std::vector<String> &faltantes) {
  const String FALTAN = "Faltan: ";
  std::vector<String> pantallas;
  pantallas.push_back(hora.substring(0, 16));
  String actual;
  for (const String &aula : faltantes) {
    if (FALTAN.length() + aula.length() > 16) {  // no entra ni sola: va en su propia pantalla
      if (actual.length()) pantallas.push_back(actual);
      actual = "";
      pantallas.push_back(aula.substring(0, 16));
    } else if (!actual.length()) {
      actual = FALTAN + aula;
    } else if (actual.length() + 1 + aula.length() <= 16) {
      actual += " " + aula;
    } else {
      pantallas.push_back(actual);
      actual = FALTAN + aula;
    }
  }
  if (actual.length()) pantallas.push_back(actual);
  return pantallas;
}

void mostrarReposo() {
  if (!redConectado()) {
    lcdMensaje("Sin conexion", redCausaSinConexion());
    return;
  }
  String hora = redHora();
  auto pantallas = pantallasReposo(hora.length() ? hora : "LlaveTrack", protocoloFaltantes());
  lcdMensaje(pantallas[(millis() / LCD_ROTACION_MS) % pantallas.size()], "A:Retirar B:Dev.");
}

// LED: verde = conectado y no falta ninguna llave; naranja = falta alguna; rojo titilando =
// sin conexion (WiFi, broker o servidor)
void actualizarLed() {
  if (!redConectado()) {
    ledColor(ColorLed::ROJO_TITILANDO);
  } else {
    ledColor(protocoloFaltantes().empty() ? ColorLed::VERDE : ColorLed::NARANJA);
  }
}

// --- Eventos al servidor (de a uno: se espera la respuesta antes de mandar otro) ---

void mandarPendientes() {
  if (!redConectado() || protocoloEsperando()) return;
  if (errorParaMandar.length()) {
    JsonDocument evento;
    evento["error"] = errorParaMandar;
    evento["detalle"] = detalleError;
    protocoloEnviar("error", evento);
    errorParaMandar = "";
  } else if (inicioPendiente && estado == Estado::REPOSO) {
    JsonDocument evento;
    evento["slotsTotales"] = SLOTS;
    evento["slotsReservados"].add(SLOT_HOME);
    protocoloEnviar("inicio", evento);
    inicioPendiente = false;
  }
}

void alResponder(const String &tipo, JsonDocument &resp) {
  bool ok = resp["ok"] | false;
  if (!ok) {
    Serial.printf("[estado] El servidor rechazo %s: %s\n", tipo.c_str(),
                  (const char *)(resp["motivo"] | "?"));
    return;
  }
  if (tipo == "inicio") {
    slotReposo = resp["slotReposo"].isNull() ? -1 : resp["slotReposo"].as<int>();
    Serial.printf("[estado] slotReposo: %d\n", slotReposo);
    if (irAlReposoTrasInicio && estado == Estado::REPOSO) {
      irAlReposoTrasInicio = false;
      if (slotReposo >= 0) {  // -1: el disco esta lleno, se queda en el HOME
        lcdMensaje("LlaveTrack", "Espere...");
        discoIrAVacio(slotReposo);
        cambiarEstado(Estado::IR_A_REPOSO);
      }
    }
  }
}

// --- La maquina de estados ---

void actualizarEstado() {
  ResultadoDisco r = discoResultado();
  switch (estado) {
    case Estado::HOMING:
      if (r == ResultadoDisco::EN_CURSO) break;
      if (r == ResultadoDisco::OK) {
        Serial.printf("[estado] Homing OK: %.0f ms por slot\n", discoMsPorSlot());
        inicioPendiente = true;
        irAlReposoTrasInicio = true;
        cambiarEstado(Estado::REPOSO);
      } else {
        fallar("Error del disco", "Avisar porteria", "MOTOR_NO_GIRA",
               "el homing no encontro el tag HOME");
      }
      break;

    case Estado::IR_A_REPOSO:
      if (r == ResultadoDisco::EN_CURSO) break;
      if (r != ResultadoDisco::OK) {
        // El lugar no estaba vacio: queda donde esta. En la devolucion se va a notar.
        Serial.printf("[estado] Slot de reposo %d: %s\n", slotReposo, discoTextoResultado(r));
      }
      cambiarEstado(Estado::REPOSO);
      break;

    case Estado::REPOSO:
      if (protocoloPidioRecalibrar()) {
        empezarHoming();
        break;
      }
      mostrarReposo();
      break;

    case Estado::ERROR:
      // El LCD ya dice el error. El preceptor puede pedir recalibrar desde el servidor.
      if (protocoloPidioRecalibrar() && lectorOk) empezarHoming();
      break;
  }
}

void comandoSerie(String linea) {
  linea.trim();
  if (linea == "r") {
    redImprimirEstado();
    Serial.print("  Faltan:");
    for (const String &aula : protocoloFaltantes()) Serial.printf(" %s", aula.c_str());
    Serial.printf("\n  Estado: %s, slotReposo %d\n", nombre(estado), slotReposo);
  } else if (linea == "p") {
    String tag = discoTagEnVentana();
    Serial.printf("  Disco en el slot %d (%.2f). En la ventana: %s\n", discoSlot(),
                  discoPosicion(), tag.length() ? tag.c_str() : "nada");
  } else if (linea == "h") {
    if (lectorOk && (estado == Estado::REPOSO || estado == Estado::ERROR)) {
      empezarHoming();
    } else {
      Serial.println("  Ahora no se puede (el disco esta ocupado o falla el lector)");
    }
  } else if (linea.length()) {
    Serial.println("  Comandos: r (red), p (disco), h (homing)");
  }
}

void leerSerie() {
  static String linea;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      comandoSerie(linea);
      linea = "";
    } else {
      linea += c;
    }
  }
}

// Unos 300 ms mirando si la D esta apretada (el teclado tiene antirrebote)
bool teclaDAlEncender() {
  unsigned long inicio = millis();
  while (millis() - inicio < 300) {
    if (teclaApretada('D')) return true;
    delay(10);
  }
  return false;
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);

  ledIniciar();
  motorIniciar();
  lcdIniciar();
  lcdMensaje("LlaveTrack", "Iniciando...");
  lectorOk = rfidIniciar();
  discoIniciar();
  // Unas lecturas antes de girar: si el HOME ya esta en la ventana, el homing lo sabe
  if (lectorOk) {
    for (int i = 0; i < 5; i++) discoActualizar();
  }

  modoDiagnostico = teclaDAlEncender();
  if (modoDiagnostico) {
    diagnosticoIniciar(lectorOk);
    return;
  }

  Serial.println("\nLlaveTrack: firmware, paso 2a (la red)");
  redIniciar(protocoloAlMensaje);
  protocoloIniciar();
  if (lectorOk) {
    empezarHoming();
  } else {
    fallar("Error: lector", "Revisar cables", "LECTOR_NO_RESPONDE", "el RC522 no responde");
  }
}

void loop() {
  if (modoDiagnostico) {
    diagnosticoLoop();
    return;
  }

  if (lectorOk) discoActualizar();
  // Reconectar al broker traba unos segundos: solo con el disco quieto
  redActualizar(discoResultado() != ResultadoDisco::EN_CURSO);
  protocoloActualizar();

  if (redConexiones() != ultimaConexion) {  // se (re)conecto al broker: avisar como esta el disco
    ultimaConexion = redConexiones();
    if (discoListo()) inicioPendiente = true;
  }
  JsonDocument resp;
  if (protocoloRespuesta(resp)) alResponder(protocoloTipoPendiente(), resp);
  mandarPendientes();

  actualizarEstado();
  actualizarLed();
  ledActualizar();

  char t = teclaLeer();
  if (t) Serial.printf("[teclado] %c (el retiro y la devolucion son el paso 2b)\n", t);
  leerSerie();
}
