// Modo diagnostico: se entra manteniendo apretada la tecla D al encender. Sin red: sirve para
// probar el disco (lo que era el paso 1) y para armar el seed (que tag hay en cada slot).
//
// Al entrar escanea el bus I2C y hace el homing. Despues se lo prueba desde el Monitor Serie
// (115200 baudios) o desde el teclado:
//
//   Monitor Serie                  Teclado
//   h          homing de nuevo
//   i 5        ir al slot 5        numero + #   (ej. 5#)
//   b A94B37A4 1   buscar esa llave, esperada en el slot 1
//   v 31       ir al slot 31 y confirmar que este vacio
//   d          una vuelta mostrando que tag hay en cada slot                  D
//   s          parar               C
//   p          donde esta el disco

#include "diagnostico.h"

#include <Wire.h>

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

void diagnosticoIniciar(bool lector) {
  lectorOk = lector;
  Serial.println("\nLlaveTrack: MODO DIAGNOSTICO (sin red)");
  lcdMensaje("Diagnostico", "Sin red");

  // Escaneo del bus I2C: el LCD suele estar en 0x27 o 0x3F
  Serial.print("[i2c] Dispositivos:");
  int encontrados = 0;
  for (byte direccion = 1; direccion < 127; direccion++) {
    Wire.beginTransmission(direccion);
    if (Wire.endTransmission() == 0) {
      Serial.printf(" 0x%02X", direccion);
      encontrados++;
    }
  }
  Serial.println(encontrados ? "" : " ninguno (revisar SDA 21, SCL 22 y la alimentacion)");

  if (!lectorOk) {
    lcdMensaje("Error: lector", "Revisar cables");
    ledColor(ColorLed::ROJO_TITILANDO);
    return;
  }
  Serial.println("  Comandos: h, i N, b UID N, v N, d, s, p");
  comandoSerie("h");
}

void diagnosticoLoop() {
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
