// Pines y constantes del equipo. Los tiempos son iniciales: se ajustan probando.
#pragma once
#include <Arduino.h>

// --- Pines: el cableado que hicieron los companeros (docs/cableado.md) ---
// RC522 por SPI: SCK 18, MISO 19, MOSI 23 (pines fijos del ESP32)
constexpr int PIN_RFID_SS = 5;
constexpr int PIN_RFID_RST = 27;
// LCD por I2C
constexpr int PIN_I2C_SDA = 21;
constexpr int PIN_I2C_SCL = 22;
// Motor por el canal B del L298N. ENB tiene el jumper: siempre a velocidad maxima
constexpr int PIN_MOTOR_IN3 = 25;
constexpr int PIN_MOTOR_IN4 = 26;
// Un LED bicolor
constexpr int PIN_LED_VERDE = 12;  // ojo: si esta en alto al arrancar, el ESP32 no prende
constexpr int PIN_LED_ROJO = 15;
// Teclado 4x4
constexpr byte PINES_FILAS[4] = {4, 13, 14, 16};
constexpr byte PINES_COLUMNAS[4] = {17, 32, 33, 2};

// --- Disco ---
constexpr int SLOTS = 32;
constexpr int SLOT_HOME = 0;                    // nunca lleva llave
constexpr const char *UID_HOME = "9A35EA81";    // leido con NFC Tools el 27/10/2026

// Una vuelta tarda 25 s (medido el 27/10/2026). Al arrancar se vuelve a medir.
constexpr unsigned long VUELTA_MS_INICIAL = 25000;
// Si en este tiempo no aparece el HOME: el motor no gira o el tag HOME no esta
constexpr unsigned long HOMING_TIMEOUT_MS = 40000;

// Sentido: true si al girar "adelante" (IN3 alto) pasan por la ventana los slots 1, 2, 3...
// Si el modo diagnostico muestra la 101 en el slot 31 (y no en el 1), cambiar a false.
constexpr bool ADELANTE_SUMA_SLOTS = true;

// Frenar un poco antes por la inercia del disco, en slots (0,1 = un decimo de slot)
constexpr float ADELANTO_FRENO_SLOTS = 0.0;
// Cuanto dura el freno (los dos IN en alto) antes de soltar el motor
constexpr unsigned long FRENO_MS = 300;

// Lector: un tag que no se lee durante este tiempo ya salio de la ventana
constexpr unsigned long TAG_AUSENTE_MS = 150;
// Al llegar a un slot, cuanto se mira el lector para confirmar que esta (o que no hay nada)
constexpr unsigned long VERIFICAR_MS = 500;

// --- Retiro y devolucion (se usan en el paso 2) ---
constexpr unsigned long RETIRO_ESTABLE_MS = 1500;  // la llave dejo de leerse = la retiraron
constexpr unsigned long DEVOLUCION_ESTABLE_MS = 1000;
constexpr unsigned long RETIRO_TIMEOUT_MS = 60000;
