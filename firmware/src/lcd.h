// LCD 16x2 por I2C. Busca solo la direccion (0x27 o 0x3F).
#pragma once
#include <Arduino.h>

void lcdIniciar();
// Muestra dos lineas. Recorta a 16 caracteres y no reescribe si no cambio (asi no parpadea).
// Sin tildes ni enie: el juego de caracteres del LCD no las tiene.
void lcdMensaje(const String &linea1, const String &linea2 = "");
