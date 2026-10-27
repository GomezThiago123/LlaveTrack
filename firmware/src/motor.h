// Motorreductor de continua por el L298N. Sin control de velocidad (ENB con jumper).
#pragma once

void motorIniciar();
// sentido: +1 adelante (IN3 alto), -1 atras (IN4 alto)
void motorGirar(int sentido);
// Freno: los dos IN en alto un rato (frena el motor en seco) y despues lo suelta
void motorFrenar();
// Llamar en cada vuelta del loop: suelta el freno cuando paso FRENO_MS
void motorActualizar();
bool motorGirando();
