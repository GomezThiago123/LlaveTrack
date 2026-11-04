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
// Corregido el 03/11/2026 (Thiago leyo los tags): 9A35EA81, que se usaba antes, es la llave de la 104
constexpr const char *UID_HOME = "A94B37A4";

// Una vuelta tarda entre 42 y 46,4 s segun la corrida (medido por el homing en el equipo real el
// 03/11/2026; antes se estimaba en 25 s). Al arrancar se vuelve a medir: esto es solo el valor
// inicial (y de el sale el timeout del homing, por eso se toma el mas lento).
constexpr unsigned long VUELTA_MS_INICIAL = 46000;
// Si en este tiempo no aparece el HOME: el motor no gira o el tag HOME no esta.
// Una vuelta y media: tiene que alcanzar para ver el HOME dos veces si arranca justo despues.
constexpr unsigned long HOMING_TIMEOUT_MS = VUELTA_MS_INICIAL * 3 / 2;

// Sentido: true si al girar "adelante" (IN3 alto) pasan por la ventana los slots 1, 2, 3...
// Medido el 04/11/2026: girando adelante pasan el HOME, 101, 102, 104, 213, 214 y 313, asi que con
// true quedan 101=1, 102=2, 104=3, 213=4, 214=5, 313=6 (los slots del seed). OJO: el 03/11 el motor
// giraba al reves y a la mitad de velocidad (con false); nadie dice haber tocado la conexion. Si
// vuelve a cambiar, el homing lo muestra en el orden de las trazas ("trazas" por el Monitor Serie).
constexpr bool ADELANTE_SUMA_SLOTS = true;

// Juego mecanico (engranajes, eje) al invertir el sentido: el motor gira un rato sin que el disco
// se mueva. Medido el 03/11/2026: unos 0,85 slots (~1,1 s), siempre igual, sin importar la
// distancia. Confirmado en una 2da prueba (error ~0,15 slot). Para volver a medirlo: en el modo
// diagnostico, ver donde "entra" cada tag yendo para atras (si entra antes de lo esperado, falta
// holgura; si despues, sobra).
constexpr float HOLGURA_REVERSA_SLOTS = 0.85;

// Buscando una llave: si al llegar al slot esperado todavia no aparecio, seguir este tramo antes de
// frenar. La velocidad deriva (hasta ~0,5 slot por vuelta, 03/11/2026) y la posicion estimada
// puede ir adelantada: sin esto frenaba con la llave al borde del lector y probaba los vecinos.
constexpr float BUSCAR_MARGEN_SLOTS = 0.6;

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

// --- Retiro y devolucion ---
constexpr unsigned long RETIRO_ESTABLE_MS = 1500;  // la llave dejo de leerse = la retiraron
constexpr unsigned long DEVOLUCION_ESTABLE_MS = 1000;  // una llave colgada que se lee este tiempo
constexpr unsigned long RETIRO_TIMEOUT_MS = 60000;  // la llave en la ventana y nadie la saca (US-04)
constexpr int CODIGO_DIGITOS = 6;
// Escribiendo el codigo sin tocar ninguna tecla este tiempo: vuelve al reposo
constexpr unsigned long CODIGO_INACTIVIDAD_MS = 20000;
// Codigos rechazados seguidos que bloquean el teclado, y por cuanto tiempo
constexpr int CODIGOS_MAL_MAX = 3;
constexpr unsigned long BLOQUEO_TECLADO_MS = 30000;
// Tecla B y nadie cuelga ninguna llave en este tiempo: vuelve al reposo
constexpr unsigned long DEVOLUCION_ESPERA_MS = 60000;
// Cuanto queda un aviso en el LCD ("Gracias", "Codigo invalido") antes de volver a la hora
constexpr unsigned long MENSAJE_MS = 3000;
