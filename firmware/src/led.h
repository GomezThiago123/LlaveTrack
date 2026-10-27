// LED bicolor. Colores acordados (27/10/2026):
//   verde fijo = conectado y no falta ninguna llave
//   naranja (los dos colores) = conectado y falta alguna llave
//   rojo titilando = sin conexion
#pragma once

enum class ColorLed { APAGADO, VERDE, NARANJA, ROJO_TITILANDO };

void ledIniciar();
void ledColor(ColorLed color);
// Llamar en cada vuelta del loop (para titilar)
void ledActualizar();
