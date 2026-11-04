// LED bicolor. Colores acordados (27/10/2026):
//   verde fijo = conectado y no falta ninguna llave
//   naranja (rojo fijo y un poco de verde) = conectado y falta alguna llave
//   rojo titilando = sin conexion
#pragma once

enum class ColorLed { APAGADO, VERDE, NARANJA, ROJO_TITILANDO, ROJO };  // ROJO fijo: solo para probar

void ledIniciar();
void ledColor(ColorLed color);
// Llamar en cada vuelta del loop (para titilar)
void ledActualizar();
// Cuantos ms en verde y en rojo para el naranja (para ajustarlo probando, sin recompilar)
void ledRepartoNaranja(int msVerde, int msRojo);
void ledImprimirEstado();  // por el Monitor Serie, para diagnosticar
