// Firmware del equipo LlaveTrack. PASO 1 de la Fase 3: el disco, sin red.
//
// Al prender, busca el tag HOME y mide cuanto tarda una vuelta. Despues se lo prueba desde el
// Monitor Serie (115200 baudios, "Nueva linea") o desde el teclado:
//
//   Monitor Serie                  Teclado
//   h          homing de nuevo
//   i 5        ir al slot 5        numero + #   (ej. 5#)
//   b A94B37A4 1   buscar esa llave, esperada en el slot 1
//   v 31       ir al slot 31 y confirmar que este vacio
//   d          diagnostico: una vuelta mostrando que tag hay en cada slot     D
//   s          parar               C
//   p          donde esta el disco
//
// El paso 2 agrega WiFi, MQTT y el retiro y la devolucion completos.

#include <Arduino.h>

#include "config.h"
#include "disco.h"
#include "lcd.h"
#include "led.h"
#include "motor.h"
#include "rfid.h"
#include "teclado.h"

namespace {
bool lectorOk = false;
bool trabajando = false;   // hay una tarea del disco en curso
String descripcion;        // que se le pidio, para mostrar el resultado
String numeroTeclado;      // lo que se va escribiendo en el teclado

void empezar(const String &que) {
  descripcion = que;
  trabajando = true;
  Serial.printf("> %s\n", que.c_str());
  ledColor(ColorLed::NARANJA);
}

void mostrarDondeEsta() {
  String tag = discoTagEnVentana();
  Serial.printf("  Disco en el slot %d (%.2f). En la ventana: %s\n", discoSlot(), discoPosicion(),
                tag.length() ? tag.c_str() : "nada");
  lcdMensaje("Slot " + String(discoSlot()), tag.length() ? tag : "vacio");
}

void alTerminar() {
  ResultadoDisco r = discoResultado();
  Serial.printf("< %s: %s\n", descripcion.c_str(), discoTextoResultado(r));
  if (r == ResultadoDisco::OK) {
    ledColor(ColorLed::VERDE);
    mostrarDondeEsta();
  } else {
    ledColor(ColorLed::ROJO_TITILANDO);
    lcdMensaje("Error:", discoTextoResultado(r));
  }
}

void comandoSerie(String linea) {
  linea.trim();
  if (!linea.length()) return;
  char c = linea[0];
  String resto = linea.substring(1);
  resto.trim();
  int espacio = resto.indexOf(' ');

  if (c != 'h' && c != 's' && c != 'p' && !discoListo()) {
    Serial.println("  Primero tiene que terminar el homing ('h')");
    return;
  }
  switch (c) {
    case 'h':
      empezar("homing");
      lcdMensaje("Buscando HOME", "Espere...");
      discoHoming();
      break;
    case 'i':
      empezar("ir al slot " + resto);
      discoIrA(resto.toInt());
      break;
    case 'b': {
      String uid = espacio > 0 ? resto.substring(0, espacio) : resto;
      uid.toUpperCase();
      int slot = espacio > 0 ? resto.substring(espacio + 1).toInt() : discoSlot();
      empezar("buscar " + uid + " (esperada en el slot " + String(slot) + ")");
      lcdMensaje("Buscando", uid);
      discoBuscar(uid, slot);
      break;
    }
    case 'v':
      empezar("ir al slot vacio " + resto);
      discoIrAVacio(resto.toInt());
      break;
    case 'd':
      empezar("diagnostico");
      lcdMensaje("Diagnostico", "Una vuelta...");
      discoDiagnostico();
      break;
    case 's':
      discoParar();
      Serial.println("  Parado");
      break;
    case 'p':
      mostrarDondeEsta();
      break;
    default:
      Serial.println("  Comandos: h, i N, b UID N, v N, d, s, p");
  }
}

void tecla(char t) {
  if (t >= '0' && t <= '9') {
    numeroTeclado += t;
    lcdMensaje("Ir al slot:", numeroTeclado);
  } else if (t == '*') {
    numeroTeclado = "";
    lcdMensaje("Ir al slot:", "");
  } else if (t == '#' && numeroTeclado.length()) {
    comandoSerie("i " + numeroTeclado);
    numeroTeclado = "";
  } else if (t == 'D') {
    comandoSerie("d");
  } else if (t == 'C') {
    comandoSerie("s");
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nLlaveTrack: firmware, paso 1 (el disco, sin red)");

  ledIniciar();
  motorIniciar();
  lcdIniciar();
  lcdMensaje("LlaveTrack", "Iniciando...");
  lectorOk = rfidIniciar();
  discoIniciar();
  if (!lectorOk) {
    lcdMensaje("Error: lector", "Revisar cables");
    ledColor(ColorLed::ROJO_TITILANDO);
    return;
  }
  // Unas lecturas antes de girar: si el HOME ya esta en la ventana, el homing lo sabe
  for (int i = 0; i < 5; i++) discoActualizar();
  comandoSerie("h");
}

void loop() {
  ledActualizar();
  if (!lectorOk) return;

  discoActualizar();
  if (trabajando && discoResultado() != ResultadoDisco::EN_CURSO) {
    trabajando = false;
    alTerminar();
  }

  char t = teclaLeer();
  if (t) tecla(t);

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
