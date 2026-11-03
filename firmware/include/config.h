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

// Una vuelta tarda 42 s (medido por el homing en el equipo real el 03/11/2026; antes se
// estimaba en 25 s). Al arrancar se vuelve a medir: esto es solo el valor inicial.
constexpr unsigned long VUELTA_MS_INICIAL = 42000;
// Si en este tiempo no aparece el HOME: el motor no gira o el tag HOME no esta.
// Una vuelta y media: tiene que alcanzar para ver el HOME dos veces si arranca justo despues.
constexpr unsigned long HOMING_TIMEOUT_MS = VUELTA_MS_INICIAL * 3 / 2;

// Sentido: true si al girar "adelante" (IN3 alto) pasan por la ventana los slots 1, 2, 3...
// Si el modo diagnostico muestra la 101 en el slot 31 (y no en el 1), cambiar a false.
constexpr bool ADELANTE_SUMA_SLOTS = true;

// Juego mecanico (engranajes, eje) al invertir el sentido: el motor gira un rato sin que el disco
// se mueva. Medido el 03/11/2026: unos 0,85 slots (~1,1 s), siempre igual, sin importar la
// distancia. Provisorio hasta medirlo otra vez (en el modo diagnostico, ver donde "entra" cada tag
// yendo para atras: si entra antes de lo esperado, falta holgura; si despues, sobra).
constexpr float HOLGURA_REVERSA_SLOTS = 0.85;

// Frenar un poco antes por la inercia del disco, en slots (0,1 = un decimo de slot)
constexpr float ADELANTO_FRENO_SLOTS = 0.0;
// Cuanto dura el freno (los dos IN en alto) antes de soltar el motor
constexpr unsigned long FRENO_MS = 300;

// Lector: un tag que no se lee durante este tiempo ya salio de la ventana
constexpr unsigned long TAG_AUSENTE_MS = 150;
// Al llegar a un slot, cuanto se mira el lector para confirmar que esta (o que no hay nada)
constexpr unsigned long VERIFICAR_MS = 500;

// --- Red (los datos de la WiFi y del broker van en secrets.h) ---
constexpr int MQTT_KEEPALIVE_S = 10;     // el broker publica el LWT a los ~15 s de silencio
constexpr unsigned long LATIDO_S = 30;   // "sigo vivo" al servidor
// Conectarse al broker traba el programa hasta MQTT_TIMEOUT_S: por eso solo se intenta con el
// disco quieto, cada MQTT_REINTENTO_MS
constexpr int MQTT_TIMEOUT_S = 3;
constexpr unsigned long MQTT_REINTENTO_MS = 5000;
// Si la WiFi no conecta en este tiempo, se vuelve a empezar la conexion
constexpr unsigned long WIFI_REINTENTO_MS = 30000;
// Sin respuesta del servidor en este tiempo: se reenvia el mismo evento (mismo eventId)
constexpr unsigned long RESPUESTA_TIMEOUT_MS = 5000;
constexpr const char *ZONA_HORARIA = "<-03>3";  // Argentina, sin horario de verano
// En reposo, la linea 1 del LCD rota entre la hora y las llaves que faltan
constexpr unsigned long LCD_ROTACION_MS = 3000;

// --- Retiro y devolucion (se usan en el paso 2b) ---
constexpr unsigned long RETIRO_ESTABLE_MS = 1500;  // la llave dejo de leerse = la retiraron
constexpr unsigned long DEVOLUCION_ESTABLE_MS = 1000;
constexpr unsigned long RETIRO_TIMEOUT_MS = 60000;
