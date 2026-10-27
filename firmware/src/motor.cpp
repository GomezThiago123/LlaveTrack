#include "motor.h"

#include <Arduino.h>

#include "config.h"

namespace {
int sentidoActual = 0;
bool frenando = false;
unsigned long inicioFreno = 0;

void salidas(bool in3, bool in4) {
  digitalWrite(PIN_MOTOR_IN3, in3 ? HIGH : LOW);
  digitalWrite(PIN_MOTOR_IN4, in4 ? HIGH : LOW);
}
}  // namespace

void motorIniciar() {
  pinMode(PIN_MOTOR_IN3, OUTPUT);
  pinMode(PIN_MOTOR_IN4, OUTPUT);
  salidas(false, false);
}

void motorGirar(int sentido) {
  sentidoActual = sentido;
  frenando = false;
  salidas(sentido > 0, sentido < 0);
}

void motorFrenar() {
  if (sentidoActual == 0 && !frenando) return;
  sentidoActual = 0;
  frenando = true;
  inicioFreno = millis();
  salidas(true, true);
}

void motorActualizar() {
  if (frenando && millis() - inicioFreno >= FRENO_MS) {
    frenando = false;
    salidas(false, false);
  }
}

bool motorGirando() {
  return sentidoActual != 0;
}
