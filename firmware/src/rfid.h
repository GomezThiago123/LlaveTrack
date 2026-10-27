// Lector RC522. Solo lee: que tags hay frente a la ventana. Lo usa el modulo disco.
#pragma once
#include <Arduino.h>

// false si el lector no responde (cables o alimentacion)
bool rfidIniciar();
// Los tags que hay frente al lector AHORA (hasta `maximo`), con su UID en hex en mayusculas y
// sin separadores. Devuelve cuantos leyo.
// - Ve tambien un tag que ya se habia leido (PICC_IsNewCardPresent solo lo ve una vez): sirve
//   para saber si sigue ahi.
// - Si hay dos (la llave pedida y una vecina), lee las dos: si no, el lector elegiria siempre
//   la misma y la otra quedaria invisible.
// Tarda unos 25 a 50 ms cuando no hay ningun tag.
int rfidLeerTodos(String uids[], int maximo);
