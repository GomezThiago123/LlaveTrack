#include "led.h"

#include <Arduino.h>
#include <esp_timer.h>
#include <soc/gpio_reg.h>

#include "config.h"

// El LED bicolor tiene 3 patas (verde en el 12, rojo en el 15 y la comun). El naranja es el rojo
// prendido fijo mas un poco de verde: con los dos al maximo el verde tapa al rojo y se ve verde.
// Un temporizador del ESP32 prende el verde solo NARANJA_TICKS_VERDE ms de cada
// (NARANJA_TICKS_VERDE + NARANJA_TICKS_ROJO): lo hace cada 1 ms, porque el loop() puede tardar
// hasta 50 ms por vuelta (el lector) y a esa velocidad se veria titilar.

namespace {
ColorLed color = ColorLed::APAGADO;
esp_timer_handle_t temporizador = nullptr;
bool alternando = false;
int tick = 0;
volatile uint32_t llamadas = 0;  // cuantas veces corrio el temporizador (para diagnosticar)
int ticksVerde = NARANJA_TICKS_VERDE, ticksRojo = NARANJA_TICKS_ROJO;

void encender(bool verde, bool rojo) {
  digitalWrite(PIN_LED_VERDE, verde ? HIGH : LOW);
  digitalWrite(PIN_LED_ROJO, rojo ? HIGH : LOW);
}

// Cada 1 ms: el rojo siempre prendido y el verde solo ticksVerde ms de cada (ticksVerde + ticksRojo)
void alternar(void *) {
  llamadas++;
  tick = (tick + 1) % (ticksVerde + ticksRojo);
  encender(tick < ticksVerde, true);
}

void alternarRapido(bool prender) {
  if (prender == alternando) return;
  if (prender) {
    esp_timer_start_periodic(temporizador, 1000);  // en microsegundos
  } else {
    esp_timer_stop(temporizador);
  }
  alternando = prender;
}
}  // namespace

void ledIniciar() {
  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_ROJO, OUTPUT);
  encender(false, false);
  esp_timer_create_args_t args = {};
  args.callback = alternar;
  args.name = "led";
  esp_timer_create(&args, &temporizador);
}

void ledColor(ColorLed nuevo) {
  color = nuevo;
  ledActualizar();
}

void ledActualizar() {
  alternarRapido(color == ColorLed::NARANJA);  // si deja de ser naranja, frena el temporizador
  switch (color) {
    case ColorLed::APAGADO: encender(false, false); break;
    case ColorLed::VERDE: encender(true, false); break;
    case ColorLed::NARANJA: break;  // lo maneja el temporizador
    case ColorLed::ROJO_TITILANDO: encender(false, (millis() / 500) % 2 == 0); break;
    case ColorLed::ROJO: encender(false, true); break;
  }
}

void ledImprimirEstado() {
  Serial.printf("  LED: color %d, temporizador %s (%s), %lu llamadas, reparto %d/%d\n", (int)color,
                alternando ? "andando" : "parado", temporizador ? "creado" : "SIN CREAR",
                (unsigned long)llamadas, ticksVerde, ticksRojo);
  // Lo que tienen de verdad los pines: 100 muestras del registro de salida en 100 ms
  int altoVerde = 0, altoRojo = 0;
  for (int i = 0; i < 100; i++) {
    uint32_t salida = REG_READ(GPIO_OUT_REG);
    altoVerde += (salida >> PIN_LED_VERDE) & 1;
    altoRojo += (salida >> PIN_LED_ROJO) & 1;
    delay(1);
  }
  Serial.printf("  Pines: verde (%d) en alto %d%%, rojo (%d) en alto %d%%\n", PIN_LED_VERDE, altoVerde,
                PIN_LED_ROJO, altoRojo);
}

void ledRepartoNaranja(int msVerde, int msRojo) {
  if (msVerde < 0 || msRojo < 0 || msVerde + msRojo == 0) return;
  ticksVerde = msVerde;
  ticksRojo = msRojo;
  tick = 0;
}
