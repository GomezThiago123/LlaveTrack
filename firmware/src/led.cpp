#include "led.h"

#include <Arduino.h>

#include "config.h"

namespace {
ColorLed color = ColorLed::APAGADO;

void encender(bool verde, bool rojo) {
  digitalWrite(PIN_LED_VERDE, verde ? HIGH : LOW);
  digitalWrite(PIN_LED_ROJO, rojo ? HIGH : LOW);
}
}  // namespace

void ledIniciar() {
  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_ROJO, OUTPUT);
  encender(false, false);
}

void ledColor(ColorLed nuevo) {
  color = nuevo;
  ledActualizar();
}

void ledActualizar() {
  switch (color) {
    case ColorLed::APAGADO: encender(false, false); break;
    case ColorLed::VERDE: encender(true, false); break;
    case ColorLed::NARANJA: encender(true, true); break;
    case ColorLed::ROJO_TITILANDO: encender(false, (millis() / 500) % 2 == 0); break;
  }
}
