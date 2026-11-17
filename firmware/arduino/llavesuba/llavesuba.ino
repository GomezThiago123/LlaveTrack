// LlavesUBA: firmware del equipo en un solo archivo, para el Arduino IDE.
//
// NO EDITAR ESTE ARCHIVO: se genera con firmware/generar_ino.py a partir de firmware/src e
// include. Los cambios van en esos archivos y despues se vuelve a generar este.
//
// Para grabarlo con el Arduino IDE:
//   - Placa: "ESP32 Dev Module", con el paquete "esp32 by Espressif Systems" version 2.0.17
//     (Herramientas > Placa > Gestor de tarjetas). Es la que usa PlatformIO; con la 3.x no esta
//     probado.
//   - Partition Scheme: "Default 4MB with spiffs" (el programa ocupa ~1 MB de 1,2 MB).
//   - Librerias (Herramientas > Administrar bibliotecas), con estas versiones:
//       MFRC522 1.4.12 (GithubCommunity / miguelbalboa)
//       LiquidCrystal I2C 1.1.2 (Frank de Brabander)
//       Keypad 3.1.1 (Mark Stanley, Alexander Brevig)
//       PubSubClient 2.8 (Nick O'Leary)
//       ArduinoJson 7.4.2 (Benoit Blanchon)
//   - secrets.h (WiFi y broker) va en esta misma carpeta: es una copia de
//     firmware/include/secrets.h (ver secrets.example.h). Nunca se sube al repo.
//   - Monitor Serie: 115200 baudios y "Nueva linea".

// ===================== include/config.h =====================
// Pines y constantes del equipo. Los tiempos son iniciales: se ajustan probando.
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
// Naranja = rojo fijo + el verde prendido NARANJA_TICKS_VERDE ms de cada (VERDE + ROJO) ms. Si se ve
// muy verde, subir NARANJA_TICKS_ROJO; si se ve rojo, bajarlo. Se prueba sin recompilar con
// "led V R" por el Monitor Serie (ej. "led 1 3").
constexpr int NARANJA_TICKS_VERDE = 1;
constexpr int NARANJA_TICKS_ROJO = 3;
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
// US-18: el DNI se escribe en lugar del codigo (7 u 8 numeros: el largo dice cual es)
constexpr int DNI_MIN_DIGITOS = 7;
constexpr int DNI_MAX_DIGITOS = 8;
// US-20: devolver una llave de otro docente: cuanto se espera que confirme con #
constexpr unsigned long CONFIRMAR_TERCERO_MS = 30000;
// US-14: devoluciones sin conexion que se guardan hasta que vuelva la red
constexpr int DEVOLUCIONES_OFFLINE_MAX = 10;
// US-10: el modo alta se cierra solo si no pasa nada en este tiempo
constexpr unsigned long MODO_ALTA_MS = 180000;
// Escribiendo el codigo sin tocar ninguna tecla este tiempo: vuelve al reposo
constexpr unsigned long CODIGO_INACTIVIDAD_MS = 20000;
// Codigos rechazados seguidos que bloquean el teclado, y por cuanto tiempo
constexpr int CODIGOS_MAL_MAX = 3;
constexpr unsigned long BLOQUEO_TECLADO_MS = 30000;
// Tecla B y nadie cuelga ninguna llave en este tiempo: vuelve al reposo
constexpr unsigned long DEVOLUCION_ESPERA_MS = 60000;
// Cuanto queda un aviso en el LCD ("Gracias", "Codigo invalido") antes de volver a la hora
constexpr unsigned long MENSAJE_MS = 3000;

// ===================== src/diagnostico.h =====================
// Modo diagnostico (tecla D apretada al encender): el disco sin red, comandos por Monitor Serie.

// El hardware ya tiene que estar iniciado (lo hace main). lector: si el RC522 respondio.
void diagnosticoIniciar(bool lector);
void diagnosticoLoop();

// ===================== src/disco.h =====================
// Donde esta el disco y como moverlo.
//
// El motor es de continua: no sabe cuanto giro. La posicion se estima por TIEMPO (milisegundos
// por slot, medidos al arrancar entre dos pasadas por el tag HOME) y se corrige cada vez que el
// lector ve el HOME. Para entregar una llave no hace falta precision: el disco gira hasta que el
// lector ve ESE UID y se centra en el.
//
// Todo es "no bloqueante": se arranca una tarea y discoActualizar() (en cada vuelta del loop)
// la va avanzando. Mientras, el resto del programa sigue andando (teclado, red, LCD).
#include <Arduino.h>

enum class ResultadoDisco {
  EN_CURSO,
  OK,
  HOME_NO_ENCONTRADO,  // en una vuelta y media no aparecio el HOME: el motor no gira o falta el tag
  UID_NO_ENCONTRADO,   // la llave pedida no esta en el disco
  SLOT_OCUPADO,        // se pidio un lugar vacio y hay un tag
};

void discoIniciar();
void discoActualizar();

// Tareas: una a la vez (la nueva reemplaza a la anterior). El resultado: discoResultado().
void discoHoming();                                     // busca el HOME y mide la vuelta
void discoIrA(int slot);                                // por tiempo, por el camino mas corto
void discoBuscar(const String &uid, int slotEsperado);  // el slot esperado, sus vecinos y una vuelta
void discoIrAVacio(int slot);                           // va al slot y confirma que no haya ningun tag
void discoDiagnostico();                                // una vuelta anotando que tag hay en cada slot
void discoParar();
// Imprime por Serial cada tag que entra y sale del lector, con la posicion (modo diagnostico)
void discoTrazas(bool activar);

ResultadoDisco discoResultado();
const char *discoTextoResultado(ResultadoDisco resultado);
bool discoListo();         // ya hizo el homing: sabe donde esta
int discoSlot();           // slot frente a la ventana (redondeado)
float discoPosicion();     // con decimales
float discoMsPorSlot();
bool discoTagPresente(const String &uid);  // ese tag esta frente al lector ahora
bool discoHayTag();                        // hay algun tag frente al lector
String discoTagEnVentana();                // el ultimo tag leido que sigue presente ("" si no hay)

// ===================== src/lcd.h =====================
// LCD 16x2 por I2C. Busca solo la direccion (0x27 o 0x3F).
#include <Arduino.h>

void lcdIniciar();
// Muestra dos lineas. Recorta a 16 caracteres y no reescribe si no cambio (asi no parpadea).
// Sin tildes ni enie: el juego de caracteres del LCD no las tiene.
void lcdMensaje(const String &linea1, const String &linea2 = "");

// ===================== src/led.h =====================
// LED bicolor. Colores acordados (27/10/2026):
//   verde fijo = conectado y no falta ninguna llave
//   naranja (rojo fijo y un poco de verde) = conectado y falta alguna llave
//   rojo titilando = sin conexion

enum class ColorLed { APAGADO, VERDE, NARANJA, ROJO_TITILANDO, ROJO };  // ROJO fijo: solo para probar

void ledIniciar();
void ledColor(ColorLed color);
// Llamar en cada vuelta del loop (para titilar)
void ledActualizar();
// Cuantos ms en verde y en rojo para el naranja (para ajustarlo probando, sin recompilar)
void ledRepartoNaranja(int msVerde, int msRojo);
void ledImprimirEstado();  // por el Monitor Serie, para diagnosticar

// ===================== src/memoria.h =====================
// Lo que el equipo tiene que recordar aunque se corte la luz (memoria flash, con Preferences):
//   - US-15: el retiro que estaba entregando. Al volver la luz se avisa al servidor, que cancela
//     la reserva (asi no queda a nombre del docente una llave que nunca recibio).
//   - US-14: las devoluciones hechas sin conexion, con su hora, para mandarlas al volver.
#include <Arduino.h>

void memoriaIniciar();

// US-15
void memoriaGuardarRetiro(const String &codigo);
void memoriaBorrarRetiro();
String memoriaRetiroInterrumpido();  // "" si no habia ningun retiro en curso

// US-14: cola de devoluciones (la mas vieja primero)
struct DevolucionGuardada {
  String uid;
  int slot;
  uint32_t hora;  // segundos desde 1970 (UTC); 0 si el equipo no sabia la hora
};
bool memoriaAgregarDevolucion(const DevolucionGuardada &devolucion);  // false si esta llena
bool memoriaPrimeraDevolucion(DevolucionGuardada &devolucion);       // false si no hay
void memoriaQuitarPrimeraDevolucion();
int memoriaDevolucionesGuardadas();

// ===================== src/motor.h =====================
// Motorreductor de continua por el L298N. Sin control de velocidad (ENB con jumper).

void motorIniciar();
// sentido: +1 adelante (IN3 alto), -1 atras (IN4 alto)
void motorGirar(int sentido);
// Freno: los dos IN en alto un rato (frena el motor en seco) y despues lo suelta
void motorFrenar();
// Llamar en cada vuelta del loop: suelta el freno cuando paso FRENO_MS
void motorActualizar();
bool motorGirando();

// ===================== src/protocolo.h =====================
// Los mensajes JSON con el servidor (docs/protocolo-mqtt.md).
//
// Eventos: se manda uno a la vez y se reenvia con el MISMO eventId cada RESPUESTA_TIMEOUT_MS (y
// al reconectar) hasta que llega su respuesta. PubSubClient publica con QoS 0, asi que la
// confiabilidad es esta: el servidor descarta los repetidos y vuelve a mandar la respuesta.
#include <Arduino.h>
#include <ArduinoJson.h>

#include <vector>

void protocoloIniciar();  // despues de redIniciar(): el numero al azar del eventId necesita la radio
void protocoloActualizar();
// Lo que llega por MQTT (se lo pasa el modulo red)
void protocoloAlMensaje(const String &sufijo, const byte *datos, unsigned int largo);

// Manda un evento nuevo (en evt/{tipo}). Le agrega el eventId. Reemplaza al que estaba esperando.
void protocoloEnviar(const char *tipo, JsonDocument &datos);
bool protocoloEsperando();   // hay un evento sin respuesta
String protocoloTipoPendiente();  // el tipo del ultimo evento mandado
int protocoloIntentos();     // cuantas veces se mando (2 o mas = hubo que reintentar)
void protocoloCancelar();    // deja de esperar la respuesta
// La respuesta al ultimo evento, una sola vez: true si llego (y la copia en `respuesta`)
bool protocoloRespuesta(JsonDocument &respuesta);

// Aulas cuya llave esta prestada (US-23). Vacia hasta que llega el mensaje retenido.
const std::vector<String> &protocoloFaltantes();
// El codigo de una reserva hecha en la web, para entregarla ya (comando entregar). "" si no hay;
// lo devuelve una sola vez
String protocoloEntregaPedida();
// true una vez si el servidor mando el comando modo_alta (US-10)
bool protocoloPidioModoAlta();
// true una vez si el servidor mando el comando recalibrar
bool protocoloPidioRecalibrar();

// ===================== src/red.h =====================
// WiFi + MQTT con reconexion, y la hora por NTP.
//
// Todo sin bloquear, salvo conectarse al broker (hasta MQTT_TIMEOUT_S): eso solo se intenta
// cuando el programa avisa que puede esperar (el disco esta quieto).
//
// Topicos (docs/protocolo-mqtt.md), con el prefijo llavetrack/v1/{DEVICE_ID}/:
//   publica   estado (retenido, con LWT), latido, evt/{tipo}
//   recibe    resp, cmd, faltantes y llavetrack/v1/servidor/estado
#include <Arduino.h>

// Lo que llega en resp, cmd o faltantes: el sufijo del topico ("resp") y el JSON
using FuncionMensaje = void (*)(const String &sufijo, const byte *datos, unsigned int largo);

void redIniciar(FuncionMensaje alMensaje);
// Llamar en cada vuelta del loop. puedeEsperar: si se puede trabar unos segundos para
// reconectar al broker (no con el disco girando).
void redActualizar(bool puedeEsperar);

bool redBrokerConectado();
// WiFi + broker + servidor online: se pueden entregar y recibir llaves
bool redConectado();
// Por que no hay conexion: "WiFi", "Broker" o "Servidor" ("" si la hay)
const char *redCausaSinConexion();
// Cuantas veces se conecto al broker desde que arranco: si cambia, hubo una reconexion
unsigned redConexiones();

// Publica en llavetrack/v1/{DEVICE_ID}/{sufijo}. false si no hay broker.
bool redPublicar(const String &sufijo, const String &json, bool retenido = false);

// "Mar 20/10  14:32", o "" si todavia no hay hora (NTP)
String redHora();
// Para el comando de diagnostico: WiFi, IP, senal, broker, servidor
void redImprimirEstado();

// ===================== src/rfid.h =====================
// Lector RC522. Solo lee: que tags hay frente a la ventana. Lo usa el modulo disco.
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

// ===================== src/teclado.h =====================
// Teclado 4x4. Teclas: A retirar, B devolver, C cancelar, * borrar, # confirmar, D diagnostico.

// La tecla que se acaba de apretar, o 0 si no hay ninguna
char teclaLeer();
// true si la tecla esta apretada ahora (para el modo diagnostico al encender)
bool teclaApretada(char tecla);

// ===================== src/diagnostico.cpp =====================
// Modo diagnostico: se entra manteniendo apretada la tecla D al encender. Sin red: sirve para
// probar el disco (lo que era el paso 1) y para armar el seed (que tag hay en cada slot).
//
// Al entrar escanea el bus I2C y hace el homing. Despues se lo prueba desde el Monitor Serie
// (115200 baudios) o desde el teclado:
//
//   Monitor Serie                  Teclado
//   h          homing de nuevo
//   i 5        ir al slot 5        numero + #   (ej. 5#)
//   b 9AAFF281 1   buscar esa llave (la 101), esperada en el slot 1
//   v 31       ir al slot 31 y confirmar que este vacio
//   d          una vuelta mostrando que tag hay en cada slot                  D
//   s          parar               C
//   p          donde esta el disco


#include <Wire.h>


namespace {
  bool lectorDiagOk = false;
  bool trabajando = false;   // hay una tarea del disco en curso
  String descripcion;        // que se le pidio, para mostrar el resultado
  String numeroTeclado;      // lo que se va escribiendo en el teclado

  void empezar(const String &que) {
    descripcion = que;
    trabajando = true;
    Serial.printf("> %s\n", que.c_str());
    ledColor(ColorLed::NARANJA);
  }

  void mostrarDondeEsta() {
    String tag = discoTagEnVentana();
    Serial.printf("  Disco en el slot %d (%.2f). En la ventana: %s\n", discoSlot(), discoPosicion(),
                  tag.length() ? tag.c_str() : "nada");
    lcdMensaje("Slot " + String(discoSlot()), tag.length() ? tag : "vacio");
  }

  void alTerminar() {
    ResultadoDisco r = discoResultado();
    Serial.printf("< %s: %s\n", descripcion.c_str(), discoTextoResultado(r));
    if (r == ResultadoDisco::OK) {
      ledColor(ColorLed::VERDE);
      mostrarDondeEsta();
    } else {
      ledColor(ColorLed::ROJO_TITILANDO);
      lcdMensaje("Error:", discoTextoResultado(r));
    }
  }

  void comandoDiagnostico(String linea) {
    linea.trim();
    if (!linea.length()) return;
    char c = linea[0];
    String resto = linea.substring(1);
    resto.trim();
    int espacio = resto.indexOf(' ');

    if (c != 'h' && c != 's' && c != 'p' && !discoListo()) {
      Serial.println("  Primero tiene que terminar el homing ('h')");
      return;
    }
    switch (c) {
      case 'h':
        empezar("homing");
        lcdMensaje("Buscando HOME", "Espere...");
        discoHoming();
        break;
      case 'i':
        empezar("ir al slot " + resto);
        discoIrA(resto.toInt());
        break;
      case 'b': {
        String uid = espacio > 0 ? resto.substring(0, espacio) : resto;
        uid.toUpperCase();
        int slot = espacio > 0 ? resto.substring(espacio + 1).toInt() : discoSlot();
        empezar("buscar " + uid + " (esperada en el slot " + String(slot) + ")");
        lcdMensaje("Buscando", uid);
        discoBuscar(uid, slot);
        break;
      }
      case 'v':
        empezar("ir al slot vacio " + resto);
        discoIrAVacio(resto.toInt());
        break;
      case 'd':
        empezar("diagnostico");
        lcdMensaje("Diagnostico", "Una vuelta...");
        discoDiagnostico();
        break;
      case 's':
        discoParar();
        Serial.println("  Parado");
        break;
      case 'p':
        mostrarDondeEsta();
        break;
      default:
        Serial.println("  Comandos: h, i N, b UID N, v N, d, s, p");
    }
  }

  void tecla(char t) {
    if (t >= '0' && t <= '9') {
      numeroTeclado += t;
      lcdMensaje("Ir al slot:", numeroTeclado);
    } else if (t == '*') {
      numeroTeclado = "";
      lcdMensaje("Ir al slot:", "");
    } else if (t == '#' && numeroTeclado.length()) {
      comandoDiagnostico("i " + numeroTeclado);
      numeroTeclado = "";
    } else if (t == 'D') {
      comandoDiagnostico("d");
    } else if (t == 'C') {
      comandoDiagnostico("s");
    }
  }
}  // namespace

void diagnosticoIniciar(bool lector) {
  lectorDiagOk = lector;
  Serial.println("\nLlavesUBA: MODO DIAGNOSTICO (sin red)");
  lcdMensaje("Diagnostico", "Sin red");

  // Escaneo del bus I2C: el LCD suele estar en 0x27 o 0x3F
  Serial.print("[i2c] Dispositivos:");
  int encontrados = 0;
  for (byte direccion = 1; direccion < 127; direccion++) {
    Wire.beginTransmission(direccion);
    if (Wire.endTransmission() == 0) {
      Serial.printf(" 0x%02X", direccion);
      encontrados++;
    }
  }
  Serial.println(encontrados ? "" : " ninguno (revisar SDA 21, SCL 22 y la alimentacion)");

  if (!lectorDiagOk) {
    lcdMensaje("Error: lector", "Revisar cables");
    ledColor(ColorLed::ROJO_TITILANDO);
    return;
  }
  discoTrazas(true);
  Serial.println("  Comandos: h, i N, b UID N, v N, d, s, p");
  comandoDiagnostico("h");
}

void diagnosticoLoop() {
  ledActualizar();
  if (!lectorDiagOk) return;
  discoActualizar();
  if (trabajando && discoResultado() != ResultadoDisco::EN_CURSO) {
    trabajando = false;
    alTerminar();
  }

  char t = teclaLeer();
  if (t) tecla(t);

  static String linea;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      comandoDiagnostico(linea);
      linea = "";
    } else {
      linea += c;
    }
  }
}

// ===================== src/disco.cpp =====================
#include <math.h>


namespace {

  // --- Tags frente al lector ---
  // Cada tag que aparece se anota con cuando se vio por primera y por ultima vez. Si deja de
  // verse TAG_AUSENTE_MS, "salio": con la primera y la ultima vez se calcula su centro.
  struct TagVisto {
    String uid;
    unsigned long primera = 0, ultima = 0;
    float posPrimera = 0;  // donde estimabamos el disco cuando aparecio
    bool activo = false;
    bool ignorar = false;  // diagnostico: ya estaba en la ventana al empezar (se anota en su 2da pasada)
  };
  constexpr int MAX_TAGS = 6;
  TagVisto vistos[MAX_TAGS];
  String ultimoTag;
  // Imprimir cada tag que entra y sale del lector. Los nombres internos no se repiten entre
  // modulos: generar_ino.py junta todo el firmware en un solo archivo
  bool trazasActivas = false;

  // --- Posicion ---
  float pos = 0;        // slot frente a la ventana (0 a SLOTS), estimado
  int dirSlots = 0;     // +1: pasan los slots 1, 2, 3...  -1: al reves  0: quieto
  int ultimoSentido = 0;     // el sentido del ultimo giro (aunque ahora este quieto)
  float holguraPendiente = 0;  // slots que el motor gira sin mover el disco (al invertir el sentido)
  unsigned long tAnterior = 0;
  float msPorSlot = (float)VUELTA_MS_INICIAL / SLOTS;
  float anchoTag = 0.5;  // cuantos slots dura un tag frente al lector (se mide con el HOME)
  bool listo = false;

  // --- Tarea en curso ---
  enum class Tarea { NADA, HOMING, MOVER, DIAGNOSTICO };
  Tarea tarea = Tarea::NADA;
  ResultadoDisco resultado = ResultadoDisco::OK;

  // Homing: fase 0 = esperando el primer paso completo del HOME, 1 = el segundo
  int faseHoming = 0;
  bool homeAlEmpezar = false;  // si ya estaba frente al lector, ese paso no sirve (no se vio entrar)
  unsigned long inicioHoming = 0, ultimoHomeMs = 0;
  float centro1Ms = 0;

  // Mover
  enum class Modo { IR, BUSCAR, VACIO };
  Modo modo = Modo::IR;
  float objetivo = 0;
  float restante = 0;  // slots que faltan recorrer en el sentido actual
  bool vueltaCompleta = false;
  bool margenUsado = false;  // BUSCAR: ya se siguio BUSCAR_MARGEN_SLOTS despues del slot esperado
  String uidBuscado;
  int slotEsperado = 0;
  int faseBusqueda = 0;  // 0 el esperado, 1 el siguiente, 2 el anterior, 3 una vuelta entera
  int empujones = 0;
  bool llegando = false, verificando = false;
  unsigned long tLlegada = 0, inicioVerificar = 0;
  bool vioObjetivo = false, vioAlgo = false;

  // Diagnostico
  struct Marca {
    String uid;
    float desde, hasta;
  };
  constexpr int MAX_MARCAS = 40;
  Marca marcas[MAX_MARCAS];
  int cantMarcas = 0;
  float recorrido = 0;

  float normalizar(float slot) {
    float s = fmodf(slot, SLOTS);
    return s < 0 ? s + SLOTS : s;
  }

  // De `desde` a `hasta` por el camino mas corto, con signo (entre -SLOTS/2 y SLOTS/2)
  float distanciaCorta(float desde, float hasta) {
    float d = normalizar(hasta - desde);
    return d > SLOTS / 2.0f ? d - SLOTS : d;
  }

  // Distancia hasta el objetivo yendo en el sentido actual (siempre positiva)
  float distanciaEnSentido(float desde, float hasta, int sentido) {
    return sentido > 0 ? normalizar(hasta - desde) : normalizar(desde - hasta);
  }

  void girar(int sentidoSlots) {
    // Al invertir el sentido, primero se recupera el juego de los engranajes: el disco no se mueve
    if (ultimoSentido != 0 && sentidoSlots != ultimoSentido) holguraPendiente = HOLGURA_REVERSA_SLOTS;
    ultimoSentido = sentidoSlots;
    dirSlots = sentidoSlots;
    tAnterior = millis();
    // El sentido fisico del motor depende de para que lado esta numerado el disco
    bool adelante = (sentidoSlots > 0) == ADELANTE_SUMA_SLOTS;
    motorGirar(adelante ? 1 : -1);
  }

  void frenar() {
    dirSlots = 0;
    motorFrenar();
  }

  // Suma lo que giro desde la ultima vez. Devuelve cuantos slots avanzo el DISCO (sin la holgura).
  float integrar() {
    unsigned long ahora = millis();
    float avance = 0;
    if (dirSlots != 0) {
      avance = (ahora - tAnterior) / msPorSlot;
      float enVacio = min(avance, holguraPendiente);  // el motor gira pero el disco todavia no
      holguraPendiente -= enVacio;
      avance -= enVacio;
      pos = normalizar(pos + dirSlots * avance);
    }
    tAnterior = ahora;
    return avance;
  }

  void terminar(ResultadoDisco r) {
    frenar();
    tarea = Tarea::NADA;
    resultado = r;
  }

  // --- Movimiento ---

  void irHacia(float destino) {
    objetivo = normalizar(destino);
    vueltaCompleta = false;
    margenUsado = false;
    llegando = verificando = false;
    float d = distanciaCorta(pos, objetivo);
    restante = fabsf(d);
    if (restante < 0.05f) {  // ya estamos: directo a verificar
      verificando = true;
      inicioVerificar = millis();
      vioObjetivo = vioAlgo = false;
      return;
    }
    girar(d > 0 ? 1 : -1);
  }

  void darVuelta() {
    vueltaCompleta = true;
    llegando = verificando = false;
    restante = SLOTS;
    girar(1);
  }

  void empezarMover(Modo m, float destino) {
    tarea = Tarea::MOVER;
    resultado = ResultadoDisco::EN_CURSO;
    modo = m;
    faseBusqueda = 0;
    empujones = 0;
    irHacia(destino);
  }

  // Termino de mirar el lector en el slot al que llegamos
  void evaluarLlegada() {
    verificando = false;
    switch (modo) {
      case Modo::IR:
        terminar(ResultadoDisco::OK);
        return;

      case Modo::VACIO:
        if (!vioAlgo) {
          terminar(ResultadoDisco::OK);
        } else if (empujones < 3) {
          empujones++;  // el lugar no estaba justo vacio: correrse medio slot y volver a mirar
          irHacia(pos + 0.5f);
        } else {
          terminar(ResultadoDisco::SLOT_OCUPADO);
        }
        return;

      case Modo::BUSCAR:
        if (vioObjetivo) {
          terminar(ResultadoDisco::OK);
          return;
        }
        faseBusqueda++;
        if (faseBusqueda == 1) {
          irHacia(slotEsperado + 1);
        } else if (faseBusqueda == 2) {
          irHacia(slotEsperado - 1);
        } else if (faseBusqueda == 3) {
          darVuelta();
        } else {
          terminar(ResultadoDisco::UID_NO_ENCONTRADO);
        }
        return;
    }
  }

  // --- Eventos del lector ---

  void alEntrar(TagVisto &t) {
    if (trazasActivas) Serial.printf("[disco]   entra %s en %.2f\n", t.uid.c_str(), pos);
    if (tarea != Tarea::MOVER || dirSlots == 0) return;

    if (t.uid == UID_HOME) {
      // El centro del HOME esta medio tag mas adelante: ahi es el slot 0
      pos = normalizar(SLOT_HOME - dirSlots * anchoTag / 2);
      if (!vueltaCompleta) {
        restante = distanciaEnSentido(pos, objetivo, dirSlots);
        if (restante > SLOTS - 1) restante = 0;  // ya lo habiamos pasado: frenar aca
      }
    }
    if (modo == Modo::BUSCAR && t.uid == uidBuscado) {
      // Apareció la llave pedida: seguir medio tag para dejarla centrada en la ventana.
      // No se corrige la posicion con su slot: podria estar colgada en otro lugar.
      objetivo = normalizar(pos + dirSlots * anchoTag / 2);
      restante = anchoTag / 2;
      vueltaCompleta = false;
    }
  }

  void alSalir(TagVisto &t) {
    unsigned long ahora = millis();
    if (trazasActivas) {
      Serial.printf("[disco]   sale  %s en %.2f (%lu ms frente al lector)\n", t.uid.c_str(), pos,
                    t.ultima - t.primera);
    }
    if (tarea == Tarea::HOMING && t.uid == UID_HOME) {
      ultimoHomeMs = ahora;
      if (homeAlEmpezar) {  // este paso empezo antes de que lo miraramos: no sirve
        homeAlEmpezar = false;
        return;
      }
      float centroMs = (t.primera + t.ultima) / 2.0f;
      if (faseHoming == 0) {
        centro1Ms = centroMs;
        anchoTag = (t.ultima - t.primera) / msPorSlot;
        faseHoming = 1;
        Serial.printf("[disco] HOME (1ra pasada). Ahora mido la vuelta...\n");
        return;
      }
      if (centroMs - centro1Ms < VUELTA_MS_INICIAL * 0.5f) return;  // rebote: el mismo paso
      msPorSlot = (centroMs - centro1Ms) / SLOTS;
      anchoTag = (t.ultima - t.primera) / msPorSlot;
      // Sentido de los slots mientras gira "adelante"
      int sentido = ADELANTE_SUMA_SLOTS ? 1 : -1;
      pos = normalizar(SLOT_HOME + sentido * (ahora - centroMs) / msPorSlot);
      tAnterior = ahora;
      listo = true;
      Serial.printf("[disco] Vuelta: %.1f s (%.0f ms por slot). Un tag dura %.2f slots en el lector.\n",
                    msPorSlot * SLOTS / 1000, msPorSlot, anchoTag);
      terminar(ResultadoDisco::OK);
      return;
    }

    if (tarea == Tarea::DIAGNOSTICO && cantMarcas < MAX_MARCAS && !t.ignorar) {
      // Uno que entro al principio se ve dos veces (la vuelta es un poco mas larga): una alcanza
      for (int i = 0; i < cantMarcas; i++) {
        if (marcas[i].uid == t.uid) return;
      }
      float posUltima = normalizar(pos - dirSlots * (ahora - t.ultima) / msPorSlot);
      marcas[cantMarcas++] = {t.uid, t.posPrimera, posUltima};
    }
  }

  void leerLector() {
    String leidos[3];
    int n = rfidLeerTodos(leidos, 3);
    unsigned long ahora = millis();

    for (int i = 0; i < n; i++) {
      ultimoTag = leidos[i];
      TagVisto *t = nullptr;
      for (auto &v : vistos) {
        if (v.activo && v.uid == leidos[i]) t = &v;
      }
      if (t) {
        t->ultima = ahora;
        continue;
      }
      for (auto &v : vistos) {  // uno nuevo: ocupa un lugar libre
        if (!v.activo) {
          v.uid = leidos[i];
          v.primera = v.ultima = ahora;
          v.posPrimera = pos;
          v.activo = true;
          v.ignorar = false;
          alEntrar(v);
          break;
        }
      }
    }
    for (auto &v : vistos) {
      if (v.activo && ahora - v.ultima > TAG_AUSENTE_MS) {
        v.activo = false;
        alSalir(v);
      }
    }
  }

  // --- Cada tarea, en cada vuelta del loop ---

  void actualizarHoming() {
    unsigned long ahora = millis();
    unsigned long desde = ultimoHomeMs ? ultimoHomeMs : inicioHoming;
    if (ahora - desde > HOMING_TIMEOUT_MS) {
      Serial.println("[disco] No aparece el HOME: el motor no gira o el tag no esta");
      terminar(ResultadoDisco::HOME_NO_ENCONTRADO);
    }
  }

  void actualizarMover(float avance) {
    unsigned long ahora = millis();
    if (verificando) {
      for (auto &v : vistos) {
        if (!v.activo) continue;
        vioAlgo = true;
        if (v.uid == uidBuscado) vioObjetivo = true;
      }
      if (ahora - inicioVerificar >= VERIFICAR_MS) evaluarLlegada();
      return;
    }
    if (llegando) {  // esperando que el disco se quede quieto
      if (ahora - tLlegada >= FRENO_MS) {
        llegando = false;
        verificando = true;
        inicioVerificar = ahora;
        vioObjetivo = vioAlgo = false;
      }
      return;
    }
    restante -= avance;
    if (restante <= ADELANTO_FRENO_SLOTS) {
      if (vueltaCompleta) {  // dio la vuelta entera sin ver la llave
        terminar(ResultadoDisco::UID_NO_ENCONTRADO);
        return;
      }
      // Buscando: la llave todavia no aparecio. Seguir un poco (la posicion estimada puede ir
      // adelantada); si entra en este tramo, alEntrar() la centra
      if (modo == Modo::BUSCAR && !margenUsado && !discoTagPresente(uidBuscado)) {
        margenUsado = true;
        restante += BUSCAR_MARGEN_SLOTS;
        return;
      }
      frenar();
      llegando = true;
      tLlegada = ahora;
    }
  }

  void actualizarDiagnostico(float avance) {
    recorrido += avance;
    // Una vuelta y dos tags mas: asi el que estaba en la ventana al empezar (que se ignora, porque
    // no se lo vio entrar) vuelve a pasar entero
    if (recorrido < SLOTS + 2 * anchoTag) return;
    frenar();
    Serial.println("[disco] Diagnostico: que tag hay en cada slot");
    for (int i = 0; i < cantMarcas; i++) {
      float centro = normalizar(marcas[i].desde + distanciaCorta(marcas[i].desde, marcas[i].hasta) / 2);
      Serial.printf("  slot %2d (%5.2f): %s%s\n", (int)lroundf(centro) % SLOTS, centro, marcas[i].uid.c_str(),
                    marcas[i].uid == UID_HOME ? "  <- HOME" : "");
    }
    if (cantMarcas == 0) Serial.println("  No se leyo ningun tag");
    tarea = Tarea::NADA;
    resultado = ResultadoDisco::OK;
  }

}  // namespace

void discoIniciar() {
  for (auto &v : vistos) v.activo = false;
}

void discoActualizar() {
  motorActualizar();
  float avance = integrar();
  leerLector();
  switch (tarea) {
    case Tarea::NADA: break;
    case Tarea::HOMING: actualizarHoming(); break;
    case Tarea::MOVER: actualizarMover(avance); break;
    case Tarea::DIAGNOSTICO: actualizarDiagnostico(avance); break;
  }
}

void discoHoming() {
  tarea = Tarea::HOMING;
  resultado = ResultadoDisco::EN_CURSO;
  faseHoming = 0;
  homeAlEmpezar = discoTagPresente(UID_HOME);
  inicioHoming = millis();
  ultimoHomeMs = 0;
  listo = false;
  girar(ADELANTE_SUMA_SLOTS ? 1 : -1);  // siempre gira "adelante"
}

void discoIrA(int slot) {
  uidBuscado = "";
  empezarMover(Modo::IR, slot);
}

void discoBuscar(const String &uid, int slot) {
  uidBuscado = uid;
  slotEsperado = slot;
  empezarMover(Modo::BUSCAR, slot);
  if (discoTagPresente(uid)) {  // ya esta en la ventana
    llegando = false;
    frenar();
    verificando = true;
    inicioVerificar = millis();
    vioObjetivo = vioAlgo = false;
  }
}

void discoIrAVacio(int slot) {
  uidBuscado = "";
  empezarMover(Modo::VACIO, slot);
}

void discoDiagnostico() {
  tarea = Tarea::DIAGNOSTICO;
  resultado = ResultadoDisco::EN_CURSO;
  cantMarcas = 0;
  recorrido = 0;
  for (auto &v : vistos) v.ignorar = v.activo;
  girar(1);
}

void discoTrazas(bool activar) { trazasActivas = activar; }

void discoParar() {
  if (tarea != Tarea::NADA) terminar(ResultadoDisco::OK);
}

ResultadoDisco discoResultado() { return resultado; }

const char *discoTextoResultado(ResultadoDisco r) {
  switch (r) {
    case ResultadoDisco::EN_CURSO: return "en curso";
    case ResultadoDisco::OK: return "OK";
    case ResultadoDisco::HOME_NO_ENCONTRADO: return "no aparece el HOME";
    case ResultadoDisco::UID_NO_ENCONTRADO: return "la llave no esta en el disco";
    case ResultadoDisco::SLOT_OCUPADO: return "el lugar no esta vacio";
  }
  return "?";
}

bool discoListo() { return listo; }
int discoSlot() { return (int)lroundf(pos) % SLOTS; }
float discoPosicion() { return pos; }
float discoMsPorSlot() { return msPorSlot; }

bool discoTagPresente(const String &uid) {
  for (auto &v : vistos) {
    if (v.activo && v.uid == uid) return true;
  }
  return false;
}

bool discoHayTag() {
  for (auto &v : vistos) {
    if (v.activo) return true;
  }
  return false;
}

String discoTagEnVentana() {
  return discoTagPresente(ultimoTag) ? ultimoTag : "";
}

// ===================== src/lcd.cpp =====================
#include <LiquidCrystal_I2C.h>
#include <Wire.h>


namespace {
  LiquidCrystal_I2C *lcd = nullptr;
  String mostrado1, mostrado2;

  bool responde(byte direccion) {
    Wire.beginTransmission(direccion);
    return Wire.endTransmission() == 0;
  }

  String recortar(const String &texto) {
    return texto.length() > 16 ? texto.substring(0, 16) : texto;
  }
}  // namespace

void lcdIniciar() {
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  byte direccion = responde(0x27) ? 0x27 : responde(0x3F) ? 0x3F : 0;
  if (!direccion) {
    Serial.println("[lcd] No se encontro el LCD (0x27 ni 0x3F)");
    return;
  }
  Serial.printf("[lcd] LCD en 0x%02X\n", direccion);
  lcd = new LiquidCrystal_I2C(direccion, 16, 2);
  lcd->init();
  lcd->backlight();
}

void lcdMensaje(const String &linea1, const String &linea2) {
  String l1 = recortar(linea1), l2 = recortar(linea2);
  if (l1 == mostrado1 && l2 == mostrado2) return;
  mostrado1 = l1;
  mostrado2 = l2;
  Serial.printf("[lcd] [%-16s] [%-16s]\n", l1.c_str(), l2.c_str());
  if (!lcd) return;
  lcd->clear();
  lcd->setCursor(0, 0);
  lcd->print(l1);
  lcd->setCursor(0, 1);
  lcd->print(l2);
}

// ===================== src/led.cpp =====================
#include <Arduino.h>
#include <esp_timer.h>
#include <soc/gpio_reg.h>


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

// ===================== src/memoria.cpp =====================
#include <Preferences.h>

#include <vector>


namespace {
  Preferences memoria;  // espacio "llavetrack" en la flash

  // La cola se guarda como un solo texto: "uid,slot,hora;uid,slot,hora"
  std::vector<DevolucionGuardada> leerCola() {
    std::vector<DevolucionGuardada> cola;
    // isKey antes de leer: si la clave no existe, getString escribe un error en el Monitor
    // Serie, y esto se consulta en cada vuelta del loop() en reposo
    if (!memoria.isKey("devol")) return cola;
    String texto = memoria.getString("devol", "");
    int inicio = 0;
    while (inicio < (int)texto.length()) {
      int fin = texto.indexOf(';', inicio);
      if (fin < 0) fin = texto.length();
      String item = texto.substring(inicio, fin);
      int coma1 = item.indexOf(','), coma2 = item.lastIndexOf(',');
      if (coma1 > 0 && coma2 > coma1) {
        cola.push_back({item.substring(0, coma1), (int)item.substring(coma1 + 1, coma2).toInt(),
                        (uint32_t)strtoul(item.substring(coma2 + 1).c_str(), nullptr, 10)});
      }
      inicio = fin + 1;
    }
    return cola;
  }

  void escribirCola(const std::vector<DevolucionGuardada> &cola) {
    String texto;
    for (const auto &d : cola) {
      if (texto.length()) texto += ";";
      texto += d.uid + "," + String(d.slot) + "," + String(d.hora);
    }
    if (cola.empty()) {
      memoria.remove("devol");  // cola vacia = sin clave (asi leerCola no la busca)
    } else {
      memoria.putString("devol", texto);
    }
  }
}  // namespace

void memoriaIniciar() { memoria.begin("llavetrack", false); }

void memoriaGuardarRetiro(const String &codigo) { memoria.putString("retiro", codigo); }
void memoriaBorrarRetiro() { memoria.remove("retiro"); }
String memoriaRetiroInterrumpido() { return memoria.isKey("retiro") ? memoria.getString("retiro", "") : ""; }

bool memoriaAgregarDevolucion(const DevolucionGuardada &devolucion) {
  auto cola = leerCola();
  if ((int)cola.size() >= DEVOLUCIONES_OFFLINE_MAX) return false;
  cola.push_back(devolucion);
  escribirCola(cola);
  return true;
}

bool memoriaPrimeraDevolucion(DevolucionGuardada &devolucion) {
  auto cola = leerCola();
  if (cola.empty()) return false;
  devolucion = cola.front();
  return true;
}

void memoriaQuitarPrimeraDevolucion() {
  auto cola = leerCola();
  if (cola.empty()) return;
  cola.erase(cola.begin());
  escribirCola(cola);
}

int memoriaDevolucionesGuardadas() { return leerCola().size(); }

// ===================== src/motor.cpp =====================
#include <Arduino.h>


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

// ===================== src/protocolo.cpp =====================
#include "secrets.h"

namespace {
  // eventId = {DEVICE_ID}-{al azar, uno por arranque}-{contador}: ej. equipo-01-7f3a-0042.
  // Asi no se repite aunque el equipo se reinicie y el contador vuelva a 0.
  String arranque;
  unsigned contador = 0;

  struct Pendiente {
    bool esperando = false;
    String eventId, tipo, json;
    unsigned long enviado = 0;
    int intentos = 0;
    unsigned conexion = 0;  // redConexiones() cuando se mando: si cambia, se reenvia enseguida
  };
  Pendiente pendiente;

  bool hayRespuesta = false;
  JsonDocument ultimaRespuesta;
  std::vector<String> faltantes;
  bool recalibrar = false;
  bool modoAlta = false;  // US-10
  String entrega;  // codigo de una reserva pedida en la web: hay que entregarla (05/11/2026)

  void mandar() {
    pendiente.enviado = millis();
    pendiente.conexion = redConexiones();
    if (redPublicar("evt/" + pendiente.tipo, pendiente.json)) pendiente.intentos++;
  }
}  // namespace

void protocoloIniciar() {
  char texto[8];
  snprintf(texto, sizeof texto, "%04x", (unsigned)(esp_random() & 0xFFFF));
  arranque = texto;
}

void protocoloActualizar() {
  if (!pendiente.esperando || !redBrokerConectado()) return;
  bool reconecto = pendiente.conexion != redConexiones();
  if (reconecto || millis() - pendiente.enviado >= RESPUESTA_TIMEOUT_MS) {
    if (pendiente.intentos > 0) {
      Serial.printf("[mqtt] Sin respuesta a %s: reintento\n", pendiente.eventId.c_str());
    }
    mandar();
  }
}

void protocoloAlMensaje(const String &sufijo, const byte *datos, unsigned int largo) {
  JsonDocument doc;
  if (deserializeJson(doc, datos, largo)) {
    Serial.printf("[mqtt] JSON roto en %s: se ignora\n", sufijo.c_str());
    return;
  }
  if (sufijo == "resp") {
    // Solo sirve la respuesta al evento que estamos esperando. Otra (de un reintento
    // anterior que ya se contesto) se ignora.
    if (pendiente.esperando && pendiente.eventId == (doc["eventId"] | "")) {
      pendiente.esperando = false;
      ultimaRespuesta = doc;
      hayRespuesta = true;
    }
  } else if (sufijo == "faltantes") {
    faltantes.clear();
    for (JsonVariant aula : doc["aulas"].as<JsonArray>()) faltantes.push_back(aula.as<String>());
  } else if (sufijo == "cmd") {
    String comando = doc["comando"] | "";
    if (comando == "recalibrar") {
      recalibrar = true;
    } else if (comando == "modo_alta") {
      modoAlta = true;
    } else if (comando == "entregar") {
      entrega = doc["codigo"] | "";
    } else {
      Serial.printf("[mqtt] Comando desconocido: %s\n", comando.c_str());
    }
  }
}

void protocoloEnviar(const char *tipo, JsonDocument &datos) {
  contador++;
  char id[64];
  snprintf(id, sizeof id, "%s-%s-%04u", DEVICE_ID, arranque.c_str(), contador);
  datos["eventId"] = id;

  pendiente.esperando = true;
  pendiente.eventId = id;
  pendiente.tipo = tipo;
  pendiente.json = "";
  serializeJson(datos, pendiente.json);
  pendiente.intentos = 0;
  hayRespuesta = false;
  mandar();  // sin broker no sale: protocoloActualizar() lo manda al reconectar
}

bool protocoloEsperando() { return pendiente.esperando; }
String protocoloTipoPendiente() { return pendiente.tipo; }
int protocoloIntentos() { return pendiente.intentos; }

void protocoloCancelar() {
  pendiente.esperando = false;
  hayRespuesta = false;
}

bool protocoloRespuesta(JsonDocument &respuesta) {
  if (!hayRespuesta) return false;
  hayRespuesta = false;
  respuesta = ultimaRespuesta;
  return true;
}

const std::vector<String> &protocoloFaltantes() { return faltantes; }

bool protocoloPidioRecalibrar() {
  bool r = recalibrar;
  recalibrar = false;
  return r;
}

bool protocoloPidioModoAlta() {
  bool m = modoAlta;
  modoAlta = false;
  return m;
}

String protocoloEntregaPedida() {
  String codigo = entrega;
  entrega = "";
  return codigo;
}

// ===================== src/red.cpp =====================
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>

#include "secrets.h"

namespace {
  const char *TOPICO_SERVIDOR = "llavetrack/v1/servidor/estado";

  WiFiClient clientePlano;
  WiFiClientSecure clienteTls;
  PubSubClient mqtt;

  String prefijo;  // llavetrack/v1/equipo-01/
  String topicoEstado;
  FuncionMensaje alMensaje = nullptr;

  bool wifiAntes = false;
  bool brokerAntes = false;
  bool servidorOnline = false;
  bool horaPedida = false;
  unsigned conexiones = 0;
  unsigned long inicioWifi = 0, ultimoIntentoBroker = 0, ultimoLatido = 0;

  void empezarWifi() {
    inicioWifi = millis();
    if (WIFI_ENTERPRISE) {
      Serial.printf("[red] Conectando a la WiFi %s (WPA2-Enterprise, usuario %s)...\n", WIFI_SSID,
                    WIFI_USUARIO);
      const char *ca = strlen(WIFI_CA_PEM) ? WIFI_CA_PEM : nullptr;
      // identidad = usuario: la mayoria de las redes PEAP lo aceptan asi
      WiFi.begin(WIFI_SSID, WPA2_AUTH_PEAP, WIFI_USUARIO, WIFI_USUARIO, WIFI_CLAVE, ca);
    } else {
      Serial.printf("[red] Conectando a la WiFi %s...\n", WIFI_SSID);
      WiFi.begin(WIFI_SSID, WIFI_CLAVE);
    }
  }

  // Llega un mensaje de un topico al que estamos suscriptos
  void recibir(char *topico, byte *datos, unsigned int largo) {
    String t(topico);
    Serial.printf("[mqtt] <- %s %.*s\n", topico, (int)largo, (const char *)datos);
    if (t == TOPICO_SERVIDOR) {
      JsonDocument doc;
      if (deserializeJson(doc, datos, largo)) return;  // JSON roto: se ignora
      servidorOnline = doc["online"] | false;
      Serial.printf("[red] Servidor %s\n", servidorOnline ? "online" : "OFFLINE");
      return;
    }
    if (t.startsWith(prefijo) && alMensaje) alMensaje(t.substring(prefijo.length()), datos, largo);
  }

  bool conectarBroker() {
    Serial.printf("[red] Conectando al broker %s:%d%s...\n", MQTT_HOST, MQTT_PUERTO,
                  MQTT_TLS ? " (TLS)" : "");
    const char *usuario = strlen(MQTT_USUARIO) ? MQTT_USUARIO : nullptr;
    const char *clave = usuario ? MQTT_CLAVE : nullptr;
    // LWT: si el equipo se corta, el broker publica {"online":false} retenido en su lugar
    bool ok = mqtt.connect(DEVICE_ID, usuario, clave, topicoEstado.c_str(), 1, true,
                           "{\"online\":false}");
    if (!ok) {
      // -2: no se pudo abrir la conexion (IP, puerto o firewall). 4/5: usuario o clave.
      Serial.printf("[red] No se pudo conectar al broker (estado %d)\n", mqtt.state());
      return false;
    }
    Serial.println("[red] MQTT conectado");
    mqtt.publish(topicoEstado.c_str(), "{\"online\":true}", true);
    // Primero el estado del servidor (retenido): asi se sabe antes que los faltantes
    mqtt.subscribe(TOPICO_SERVIDOR, 1);
    mqtt.subscribe((prefijo + "resp").c_str(), 1);
    mqtt.subscribe((prefijo + "cmd").c_str(), 1);
    mqtt.subscribe((prefijo + "faltantes").c_str(), 1);
    ultimoLatido = millis();
    conexiones++;
    return true;
  }
}  // namespace

void redIniciar(FuncionMensaje funcion) {
  alMensaje = funcion;
  prefijo = String("llavetrack/v1/") + DEVICE_ID + "/";
  topicoEstado = prefijo + "estado";

  WiFi.persistent(false);  // no grabar la red en la flash en cada arranque
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);    // sin ahorro de energia: los mensajes llegan sin demora
  WiFi.setAutoReconnect(true);
  empezarWifi();

  if (MQTT_TLS) {
    if (strlen(MQTT_CA_PEM)) {
      clienteTls.setCACert(MQTT_CA_PEM);
    } else {
      Serial.println("[red] OJO: TLS sin certificado de la CA, no se verifica el broker");
      clienteTls.setInsecure();
    }
    mqtt.setClient(clienteTls);
  } else {
    mqtt.setClient(clientePlano);
  }
  IPAddress ip;
  if (ip.fromString(MQTT_HOST)) {
    mqtt.setServer(ip, MQTT_PUERTO);
  } else {
    mqtt.setServer(MQTT_HOST, MQTT_PUERTO);
  }
  mqtt.setBufferSize(512);  // con 256 (el valor por defecto) se cortan los JSON
  mqtt.setKeepAlive(MQTT_KEEPALIVE_S);
  mqtt.setSocketTimeout(MQTT_TIMEOUT_S);
  mqtt.setCallback(recibir);
  ultimoIntentoBroker = millis() - MQTT_REINTENTO_MS;  // el primer intento, enseguida
}

void redActualizar(bool puedeEsperar) {
  bool wifi = WiFi.status() == WL_CONNECTED;
  if (wifi != wifiAntes) {
    wifiAntes = wifi;
    if (wifi) {
      Serial.printf("[red] WiFi conectada: IP %s, senal %d dBm\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
      if (!horaPedida) {  // la hora sigue andando sola aunque despues se corte la red
        configTzTime(ZONA_HORARIA, "pool.ntp.org", "time.google.com");
        horaPedida = true;
      }
    } else {
      Serial.println("[red] Se corto la WiFi");
      inicioWifi = millis();
    }
  }

  if (!wifi) {
    if (millis() - inicioWifi >= WIFI_REINTENTO_MS) {
      Serial.println("[red] La WiFi no conecta: empiezo de nuevo");
      WiFi.disconnect();
      empezarWifi();
    }
  } else if (mqtt.connected()) {
    mqtt.loop();  // recibe mensajes y mantiene la conexion (keepalive)
    if (millis() - ultimoLatido >= LATIDO_S * 1000UL) {
      ultimoLatido = millis();
      redPublicar("latido", "{}");
    }
  } else if (puedeEsperar && millis() - ultimoIntentoBroker >= MQTT_REINTENTO_MS) {
    ultimoIntentoBroker = millis();
    conectarBroker();
  }

  bool broker = wifi && mqtt.connected();
  if (broker != brokerAntes) {
    brokerAntes = broker;
    if (!broker) {
      Serial.println("[red] Sin broker");
      servidorOnline = false;  // sin broker no hay forma de saber si el servidor sigue vivo
    }
  }
}

bool redBrokerConectado() { return WiFi.status() == WL_CONNECTED && mqtt.connected(); }

bool redConectado() { return redBrokerConectado() && servidorOnline; }

const char *redCausaSinConexion() {
  if (WiFi.status() != WL_CONNECTED) return "WiFi";
  if (!mqtt.connected()) return "Broker";
  if (!servidorOnline) return "Servidor";
  return "";
}

unsigned redConexiones() { return conexiones; }

bool redPublicar(const String &sufijo, const String &json, bool retenido) {
  if (!redBrokerConectado()) return false;
  String topico = prefijo + sufijo;
  Serial.printf("[mqtt] -> %s %s\n", topico.c_str(), json.c_str());
  return mqtt.publish(topico.c_str(), json.c_str(), retenido);
}

String redHora() {
  struct tm t;
  if (!getLocalTime(&t, 0)) return "";  // 0: no esperar si todavia no llego la hora
  static const char *DIAS[] = {"Dom", "Lun", "Mar", "Mie", "Jue", "Vie", "Sab"};
  char texto[24];
  snprintf(texto, sizeof texto, "%s %02d/%02d  %02d:%02d", DIAS[t.tm_wday], t.tm_mday,
           t.tm_mon + 1, t.tm_hour, t.tm_min);
  return texto;
}

void redImprimirEstado() {
  bool wifi = WiFi.status() == WL_CONNECTED;
  Serial.printf("  WiFi %s: %s", WIFI_SSID, wifi ? "conectada" : "sin conexion");
  if (wifi) Serial.printf(", IP %s, senal %d dBm", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  Serial.printf("\n  Broker %s:%d: %s (estado %d)\n", MQTT_HOST, MQTT_PUERTO,
                mqtt.connected() ? "conectado" : "sin conexion", mqtt.state());
  Serial.printf("  Servidor: %s\n", servidorOnline ? "online" : "offline");
  String hora = redHora();
  Serial.printf("  Hora: %s\n", hora.length() ? hora.c_str() : "todavia no");
}

// ===================== src/rfid.cpp =====================
#include <MFRC522.h>
#include <SPI.h>


namespace {
  MFRC522 lector(PIN_RFID_SS, PIN_RFID_RST);

  String uidActual() {
    String uid = "";
    for (byte i = 0; i < lector.uid.size; i++) {
      if (lector.uid.uidByte[i] < 0x10) uid += "0";
      uid += String(lector.uid.uidByte[i], HEX);
    }
    uid.toUpperCase();
    return uid;
  }
}  // namespace

bool rfidIniciar() {
  SPI.begin();
  lector.PCD_Init();
  byte version = lector.PCD_ReadRegister(MFRC522::VersionReg);
  bool ok = version != 0x00 && version != 0xFF;
  Serial.printf("[rfid] %s (version 0x%02X)\n", ok ? "Lector OK" : "El lector NO responde: revisar cables y 3,3 V", version);
  return ok;
}

int rfidLeerTodos(String uids[], int maximo) {
  int leidos = 0;
  // 1) WUPA despierta a todos, incluso a los que se "durmieron" (HALT) en la lectura anterior.
  //    Se lee uno y se lo duerme.
  byte atqa[2];
  byte largo = sizeof(atqa);
  MFRC522::StatusCode estado = lector.PICC_WakeupA(atqa, &largo);
  if (estado != MFRC522::STATUS_OK && estado != MFRC522::STATUS_COLLISION) return 0;
  if (!lector.PICC_ReadCardSerial()) return 0;
  uids[leidos++] = uidActual();
  lector.PICC_HaltA();
  // 2) REQA solo despierta a los que NO estan dormidos: aparecen los demas, de a uno
  while (leidos < maximo && lector.PICC_IsNewCardPresent() && lector.PICC_ReadCardSerial()) {
    uids[leidos++] = uidActual();
    lector.PICC_HaltA();
  }
  return leidos;
}

// ===================== src/teclado.cpp =====================
#include <Keypad.h>


namespace {
  char TECLAS[4][4] = {
      {'1', '2', '3', 'A'},
      {'4', '5', '6', 'B'},
      {'7', '8', '9', 'C'},
      {'*', '0', '#', 'D'},
  };
  byte filas[4] = {PINES_FILAS[0], PINES_FILAS[1], PINES_FILAS[2], PINES_FILAS[3]};
  byte columnas[4] = {PINES_COLUMNAS[0], PINES_COLUMNAS[1], PINES_COLUMNAS[2], PINES_COLUMNAS[3]};
  Keypad teclado(makeKeymap(TECLAS), filas, columnas, 4, 4);
}  // namespace

char teclaLeer() {
  char tecla = teclado.getKey();
  return tecla ? tecla : 0;
}

bool teclaApretada(char tecla) {
  teclado.getKeys();  // actualiza la lista de teclas apretadas
  return teclado.isPressed(tecla);
}

// ===================== src/main.cpp =====================
// Firmware del equipo LlavesUBA: la maquina de estados (ver CLAUDE.md, seccion Firmware).
//
// Al prender:
//   1. homing (busca el tag HOME y mide la vuelta);
//   2. se conecta a la WiFi y al broker (en paralelo, mientras gira);
//   3. manda `inicio` y el disco va al lugar vacio que responde el servidor (slotReposo).
// En reposo, el LCD muestra la hora y las llaves que faltan, y el LED la conexion.
//
// Retiro (tecla A, US-04 y US-05): el docente escribe el codigo de la web (* borra, # confirma,
// C cancela); el servidor dice que llave es y donde esta; el disco la busca por su UID y la deja
// en la ventana; cuando el lector deja de verla, el retiro se confirma. Si no aparece, repite el
// homing y la vuelve a buscar (intento 2); si tampoco, "Pedi la llave en porteria".
// Devolucion (tecla B, US-06): el docente cuelga la llave en el lugar vacio de la ventana; cuando
// el lector la ve estable, se avisa al servidor y el disco deja otro lugar vacio.
//
// Con la tecla D apretada al encender entra al modo diagnostico (diagnostico.cpp, sin red).
// Monitor Serie (115200): "r" estado de la red, "p" donde esta el disco, "h" homing de nuevo,
// "t A123456#" simula esas teclas (para probar sin tocar el teclado), "trazas" prende o apaga
// el registro de cada tag que pasa por el lector.

#include <Arduino.h>
#include <ArduinoJson.h>

#include <vector>


namespace {
  enum class Estado {
    HOMING,                // buscando el HOME (al prender o con el comando recalibrar)
    IR_A_REPOSO,           // llevando un lugar vacio a la ventana
    REPOSO,
    INGRESO_CODIGO,        // tecla A: el docente escribe su DNI (olvido el celular)
    INGRESO_AULA,          // despues del DNI: el aula que pide
    ESPERANDO_SERVIDOR,    // se mando un evento (codigo, retiro o devolucion) y falta la respuesta
    MOVIENDO,              // el disco busca la llave pedida
    REPOSICIONANDO,        // US-05, intento 2: homing de nuevo antes de volver a buscarla
    ESPERANDO_RETIRO,      // la llave esta en la ventana: el docente la tiene que sacar
    ESPERANDO_DEVOLUCION,  // tecla B: el docente tiene que colgar la llave en la ventana
    SACAR_LLAVE,           // devolucion rechazada: esperando que saquen esa llave de la ventana
    BLOQUEADO,             // muchos codigos mal seguidos: el teclado no responde un rato
    CONFIRMAR_TERCERO,     // US-20: la llave la retiro otro docente; se confirma con #
    BUSCANDO_VACIO,        // US-14: devolucion sin conexion; busca un lugar vacio sin el servidor
    MODO_ALTA,             // US-10: el preceptor acerca un tag nuevo al lector
    ERROR,                 // el disco no anda: no se entrega nada (el LCD dice por que)
  };
  Estado estado = Estado::HOMING;
  unsigned long desdeEstado = 0;  // millis() al entrar al estado actual
  bool modoDiagnostico = false;
  bool lectorOk = false;
  // Por el Monitor Serie, cada tag que entra y sale del lector con la posicion estimada. Prendidas
  // mientras se ajusta el equipo (Fase 3 y 4); el comando "trazas" las apaga.
  bool trazas = true;

  // `inicio` se manda despues de cada homing y en cada reconexion al broker
  bool inicioPendiente = false;
  unsigned ultimaConexion = 0;        // redConexiones() la ultima vez que se miro
  bool irAlReposoTrasInicio = false;  // despues del homing: el disco quedo en el HOME
  int slotReposo = -1;                // el lugar vacio frente a la ventana (-1: no se sabe)

  // Falla para avisarle al servidor (crea un incidente que ve el preceptor, US-05)
  String errorParaMandar, detalleError, codigoError;

  // Un aviso ("Gracias", "Codigo invalido") queda en el LCD hasta este momento
  unsigned long avisoHasta = 0;

  // US-15: un retiro que quedo a medias por un corte de luz. Se avisa al servidor al conectarse
  String retiroInterrumpido;
  bool retiroInterrumpidoEnviado = false;
  bool primerReposo = true;  // US-15: la primera vez que llega al reposo, "Equipo listo"
  // US-14: se esta mandando una devolucion guardada sin conexion (la respuesta la saca de la cola)
  bool mandandoGuardada = false;

  // El retiro en curso. dni: si el docente se identifico con su DNI en lugar del codigo (US-18)
  struct Retiro {
    String codigo, dni, aulaPedida, uid, aula, apellido, nombre;
    bool desdeWeb = false;  // lo pidio la web (comando entregar), no el teclado
    int slot = -1;     // donde dice el servidor que esta la llave
    int intento = 1;   // US-05: el 2do es despues de repetir el homing
    unsigned long ausenteDesde = 0;  // desde cuando el lector no ve la llave (0: la ve)
  };
  Retiro retiro;
  String codigoEscrito;          // lo que va escribiendo el docente (DNI, y despues el aula)
  String dniEscrito;
  String entregaPendiente;       // codigo de una reserva de la web que espera a que el equipo este libre
  unsigned long ultimaTecla = 0;
  int codigosMal = 0;            // rechazados seguidos (se bloquea el teclado al llegar al maximo)

  // La devolucion en curso: el tag que aparecio en la ventana y se esta viendo si queda estable.
  // Tambien vale si la llave ya estaba colgada al apretar B (algunos cuelgan primero).
  String candidato;
  unsigned long candidatoDesde = 0;
  int slotDevolucion = -1;
  // US-20: quien devuelve puede escribir su DNI (opcional) y confirmarlo con #
  String dniDevolucion;
  bool dniConfirmado = false;
  bool devolucionSinConexion = false;  // US-14: B sin conexion
  // US-14: busqueda de un lugar vacio sin el servidor: slot base y cuantos se probaron
  int vacioBase = 0, vacioIntentos = 0;
  // US-10: el ultimo tag que se mando en el modo alta (para no repetirlo)
  String tagAlta;
  unsigned long actividadAlta = 0;

  const char *nombre(Estado e) {
    switch (e) {
      case Estado::HOMING: return "HOMING";
      case Estado::IR_A_REPOSO: return "IR_A_REPOSO";
      case Estado::REPOSO: return "REPOSO";
      case Estado::INGRESO_CODIGO: return "INGRESO_CODIGO";
      case Estado::INGRESO_AULA: return "INGRESO_AULA";
      case Estado::ESPERANDO_SERVIDOR: return "ESPERANDO_SERVIDOR";
      case Estado::MOVIENDO: return "MOVIENDO";
      case Estado::REPOSICIONANDO: return "REPOSICIONANDO";
      case Estado::ESPERANDO_RETIRO: return "ESPERANDO_RETIRO";
      case Estado::ESPERANDO_DEVOLUCION: return "ESPERANDO_DEVOLUCION";
      case Estado::SACAR_LLAVE: return "SACAR_LLAVE";
      case Estado::BLOQUEADO: return "BLOQUEADO";
      case Estado::CONFIRMAR_TERCERO: return "CONFIRMAR_TERCERO";
      case Estado::BUSCANDO_VACIO: return "BUSCANDO_VACIO";
      case Estado::MODO_ALTA: return "MODO_ALTA";
      case Estado::ERROR: return "ERROR";
    }
    return "?";
  }

  void cambiarEstado(Estado nuevo) {
    if (nuevo != estado) Serial.printf("[estado] %s -> %s\n", nombre(estado), nombre(nuevo));
    estado = nuevo;
    desdeEstado = millis();
  }

  // Un mensaje que queda en el LCD unos segundos aunque el equipo vuelva al reposo
  void aviso(const String &linea1, const String &linea2, unsigned long duracion = MENSAJE_MS) {
    lcdMensaje(linea1, linea2);
    avisoHasta = millis() + duracion;
  }

  void empezarHoming() {
    lcdMensaje("Buscando HOME", "Espere...");
    discoHoming();
    cambiarEstado(Estado::HOMING);
  }

  void fallar(const char *linea1, const char *linea2, const char *error, const String &detalle,
              const String &codigo = "") {
    Serial.printf("[estado] ERROR %s: %s\n", error, detalle.c_str());
    lcdMensaje(linea1, linea2);
    errorParaMandar = error;
    detalleError = detalle;
    codigoError = codigo;
    // Un pedido de la web que esperaba (ej. llego durante el homing) ya no se puede atender: si
    // quedara guardado, saldria recien despues de recalibrar, con la reserva vencida
    entregaPendiente = "";
    cambiarEstado(Estado::ERROR);
  }

  // Deja un lugar vacio frente a la ventana (si no esta ya ahi) y vuelve al reposo
  void volverAlReposo() {
    if (slotReposo >= 0 && discoSlot() != slotReposo) {
      discoIrAVacio(slotReposo);
      cambiarEstado(Estado::IR_A_REPOSO);
    } else {
      cambiarEstado(Estado::REPOSO);
    }
  }

  // Las pantallas que rota la linea 1 del LCD en reposo (US-23): la hora y despues
  // "Faltan: 105 114" con todas las aulas que entren. Misma regla que pantallas_reposo() del
  // simulador (backend/simulador/simulador.py), que tiene tests.
  std::vector<String> pantallasReposo(const String &hora, const std::vector<String> &faltantes) {
    const String FALTAN = "Faltan: ";
    std::vector<String> pantallas;
    pantallas.push_back(hora.substring(0, 16));
    String actual;
    for (const String &aula : faltantes) {
      if (FALTAN.length() + aula.length() > 16) {  // no entra ni sola: va en su propia pantalla
        if (actual.length()) pantallas.push_back(actual);
        actual = "";
        pantallas.push_back(aula.substring(0, 16));
      } else if (!actual.length()) {
        actual = FALTAN + aula;
      } else if (actual.length() + 1 + aula.length() <= 16) {
        actual += " " + aula;
      } else {
        pantallas.push_back(actual);
        actual = FALTAN + aula;
      }
    }
    if (actual.length()) pantallas.push_back(actual);
    return pantallas;
  }

  void mostrarReposo() {
    if (millis() < avisoHasta) return;  // todavia se ve un aviso
    if (!redConectado()) {
      lcdMensaje("Sin conexion", redCausaSinConexion());
      return;
    }
    String hora = redHora();
    auto pantallas = pantallasReposo(hora.length() ? hora : "LlavesUBA", protocoloFaltantes());
    lcdMensaje(pantallas[(millis() / LCD_ROTACION_MS) % pantallas.size()], "A:Retirar B:Dev.");
  }

  // LED: verde = conectado y no falta ninguna llave; naranja = falta alguna; rojo titilando =
  // sin conexion (WiFi, broker o servidor)
  unsigned long pruebaLedHasta = 0;  // comando "led": un color unos segundos, para verlo
  ColorLed pruebaLedColor = ColorLed::NARANJA;

  void actualizarLed() {
    if (millis() < pruebaLedHasta) {
      ledColor(pruebaLedColor);
    } else if (!redConectado()) {
      ledColor(ColorLed::ROJO_TITILANDO);
    } else {
      ledColor(protocoloFaltantes().empty() ? ColorLed::VERDE : ColorLed::NARANJA);
    }
  }

  // --- Eventos al servidor (de a uno: se espera la respuesta antes de mandar otro) ---

  void mandarPendientes() {
    if (!redConectado() || protocoloEsperando()) return;
    if (retiroInterrumpido.length() && !retiroInterrumpidoEnviado) {  // US-15
      JsonDocument evento;
      evento["codigo"] = retiroInterrumpido;
      protocoloEnviar("retiro_interrumpido", evento);
      retiroInterrumpidoEnviado = true;
      return;
    }
    DevolucionGuardada guardada;
    if (estado == Estado::REPOSO && memoriaPrimeraDevolucion(guardada)) {  // US-14
      JsonDocument evento;
      evento["uid"] = guardada.uid;
      evento["slot"] = guardada.slot;
      if (guardada.hora) evento["devueltoEn"] = guardada.hora;
      protocoloEnviar("devolucion", evento);
      mandandoGuardada = true;
      return;
    }
    if (errorParaMandar.length()) {
      JsonDocument evento;
      evento["error"] = errorParaMandar;
      evento["detalle"] = detalleError;
      if (codigoError.length()) evento["codigo"] = codigoError;  // asi el servidor sabe aula y docente
      protocoloEnviar("error", evento);
      errorParaMandar = "";
    } else if (inicioPendiente && estado == Estado::REPOSO) {
      JsonDocument evento;
      evento["slotsTotales"] = SLOTS;
      evento["slotsReservados"].add(SLOT_HOME);
      protocoloEnviar("inicio", evento);
      inicioPendiente = false;
    }
  }

  void mandarSolicitudRetiro() {
    JsonDocument evento;
    // Con DNI y aula (teclado) la primera vez; despues el servidor ya dijo el codigo
    if (retiro.codigo.length()) {
      evento["codigo"] = retiro.codigo;
    } else {
      evento["dni"] = retiro.dni;
      if (retiro.aulaPedida.length()) evento["aula"] = retiro.aulaPedida;
    }
    protocoloEnviar("solicitud_retiro", evento);
    cambiarEstado(Estado::ESPERANDO_SERVIDOR);
  }

  // --- Retiro (US-04 y US-05) ---

  void mostrarCodigo() {
    String linea2 = codigoEscrito + "_";
    while (linea2.length() < 12) linea2 += " ";
    if (estado == Estado::INGRESO_AULA) {
      lcdMensaje("Aula:", linea2 + "#=OK");
    } else {
      lcdMensaje("Ingrese su DNI", linea2 + "#=OK");
    }
  }

  void empezarIngreso() {
    codigoEscrito = "";
    ultimaTecla = millis();
    avisoHasta = 0;
    cambiarEstado(Estado::INGRESO_CODIGO);
    mostrarCodigo();
  }

  // El teclado es para el docente que olvido el celular (05/11/2026): DNI, # y despues el aula, #.
  // Con la web no hace falta: "Pedir llave" ya la manda a entregar
  void confirmarCodigo() {
    int largo = codigoEscrito.length();
    if (estado == Estado::INGRESO_CODIGO) {
      if (largo < DNI_MIN_DIGITOS || largo > DNI_MAX_DIGITOS) {
        lcdMensaje("DNI: 7 u 8 nros", codigoEscrito);
        return;
      }
      dniEscrito = codigoEscrito;
      codigoEscrito = "";
      cambiarEstado(Estado::INGRESO_AULA);
      mostrarCodigo();
      return;
    }
    if (!largo) return;  // falta el aula
    if (!redConectado()) {
      aviso("Sin conexion", redCausaSinConexion());
      cambiarEstado(Estado::REPOSO);
      return;
    }
    retiro = Retiro();
    retiro.dni = dniEscrito;
    retiro.aulaPedida = codigoEscrito;
    lcdMensaje("Verificando", "Aula " + codigoEscrito);
    mandarSolicitudRetiro();
  }

  void codigoRechazado(const String &motivo) {
    if (motivo == "ERROR_INTERNO") {  // no es culpa del docente: no cuenta para el bloqueo
      aviso("Error del", "servidor");
      volverAlReposo();
      return;
    }
    if (retiro.desdeWeb) {  // la reserva de la web vencio o se cancelo: no es un intento mal
      aviso("Pedido vencido", "Pedila de nuevo");
      volverAlReposo();
      return;
    }
    // Problemas del aula (no del DNI): no cuentan para el bloqueo
    if (motivo == "AULA_NO_ENCONTRADA" || motivo == "LLAVE_NO_DISPONIBLE" || motivo == "AULA_EN_REVISION" ||
        motivo == "YA_TIENE_RESERVA") {
      if (motivo == "AULA_NO_ENCONTRADA") aviso("Aula " + retiro.aulaPedida, "no existe");
      if (motivo == "LLAVE_NO_DISPONIBLE") aviso("Aula " + retiro.aulaPedida, "no disponible");
      if (motivo == "AULA_EN_REVISION") aviso("Aula en revision", "Pedila en porteria");
      if (motivo == "YA_TIENE_RESERVA") aviso("Ya tenes otra", "reserva en la web");
      volverAlReposo();
      return;
    }
    codigosMal++;
    if (codigosMal >= CODIGOS_MAL_MAX) {
      codigosMal = 0;
      Serial.println("[estado] Demasiados codigos mal: teclado bloqueado");
      volverAlReposo();  // por si el disco quedo en el HOME (intento 2)
      cambiarEstado(Estado::BLOQUEADO);
      return;
    }
    String linea1 = motivo == "CODIGO_VENCIDO" ? "Codigo vencido" : "Codigo invalido";
    String linea2 = "Le quedan " + String(CODIGOS_MAL_MAX - codigosMal);
    if (motivo == "CREDENCIAL_NO_RECONOCIDA") {  // US-18: DNI que no es de nadie (o desactivado)
      linea1 = "Credencial no";
      linea2 = "reconocida";
    } else if (motivo == "SIN_RESERVA") {
      linea1 = "No tenes reserva";
      linea2 = "Pedila en la web";
    }
    aviso(linea1, linea2);
    volverAlReposo();
  }

  // La llave no aparecio en los dos intentos: no se entrega nada (US-05)
  void llaveNoEncontrada() {
    memoriaBorrarRetiro();  // US-15: el retiro termino (sin llave)
    aviso("Pedi la llave", "en porteria", 3 * MENSAJE_MS);
    errorParaMandar = "LLAVE_NO_ENCONTRADA";
    detalleError = "uid " + retiro.uid + ", slot " + String(retiro.slot);
    codigoError = retiro.codigo;
    volverAlReposo();
  }

  void terminarPorTiempo() {
    memoriaBorrarRetiro();  // US-15
    JsonDocument evento;
    evento["codigo"] = retiro.codigo;
    protocoloEnviar("retiro_timeout", evento);
    aviso("Tiempo agotado", "La reserva sigue");
    volverAlReposo();
  }

  void alRespuestaRetiro(bool ok, const String &motivo, JsonDocument &resp) {
    if (!ok) {
      Serial.printf("[estado] Codigo rechazado: %s\n", motivo.c_str());
      if (retiro.intento == 2) {
        llaveNoEncontrada();  // vencio mientras se repetia el homing: no es culpa del docente
      } else {
        codigoRechazado(motivo);
      }
      return;
    }
    codigosMal = 0;
    if (!retiro.codigo.length()) retiro.codigo = resp["codigo"] | "";  // US-18: vino con DNI
    retiro.nombre = resp["nombre"] | "";
    memoriaGuardarRetiro(retiro.codigo);  // US-15: si se corta la luz, al volver se cancela
    retiro.uid = resp["uid"].as<String>();
    retiro.slot = resp["slot"] | -1;
    retiro.aula = resp["aula"].as<String>();
    retiro.apellido = resp["apellido"].as<String>();
    Serial.printf("[estado] Retiro: aula %s, uid %s, slot %d (intento %d)\n", retiro.aula.c_str(),
                  retiro.uid.c_str(), retiro.slot, retiro.intento);
    if (retiro.intento == 1) {
      lcdMensaje("Hola " + retiro.nombre, "Aula " + retiro.aula);  // web o teclado: saluda igual
    }
    discoBuscar(retiro.uid, retiro.slot);
    cambiarEstado(Estado::MOVIENDO);
  }

  void alRespuestaRetiroConfirmado(bool ok, const String &motivo) {
    memoriaBorrarRetiro();  // US-15
    slotReposo = discoSlot();  // el lugar de la llave quedo vacio frente a la ventana
    if (ok) {
      aviso("Gracias", retiro.apellido);
    } else {
      // La llave ya se fue con el docente pero el servidor no lo registro (ej. se cancelo la
      // reserva desde la web mientras giraba el disco): que lo vea el preceptor
      aviso("No se registro", "Avisar porteria", 3 * MENSAJE_MS);
      errorParaMandar = "RETIRO_NO_REGISTRADO";
      detalleError = "uid " + retiro.uid + ": " + motivo;
      codigoError = retiro.codigo;
    }
    cambiarEstado(Estado::REPOSO);
  }

  // --- Devolucion (US-06) ---

  void mostrarDevolucion() {
    if (devolucionSinConexion) {
      lcdMensaje("Sin conexion", "Cuelgue la llave");  // US-14
    } else if (!dniDevolucion.length()) {
      lcdMensaje("Cuelgue la llave", "DNI+# opcional");  // US-20: para devolver una de otro
    } else {
      lcdMensaje("Cuelgue la llave", "DNI " + dniDevolucion + (dniConfirmado ? " OK" : " #"));
    }
  }

  void empezarDevolucion(bool sinConexion) {
    candidato = "";
    dniDevolucion = "";
    dniConfirmado = false;
    devolucionSinConexion = sinConexion;
    avisoHasta = 0;
    mostrarDevolucion();
    cambiarEstado(Estado::ESPERANDO_DEVOLUCION);
  }

  void mandarDevolucion(bool confirmada) {
    JsonDocument evento;
    evento["uid"] = candidato;
    evento["slot"] = slotDevolucion;
    if (dniConfirmado) evento["dni"] = dniDevolucion;  // US-20
    if (confirmada) evento["confirmada"] = true;
    protocoloEnviar("devolucion", evento);
    lcdMensaje("Verificando", "la llave...");
    cambiarEstado(Estado::ESPERANDO_SERVIDOR);
  }

  // US-14: sin servidor no se sabe que lugar esta vacio: se prueban los de al lado (+1, -1, +2...)
  // y el lector confirma que no haya nada
  void probarSiguienteVacio() {
    vacioIntentos++;
    if (vacioIntentos > 8) {  // no encontro: queda donde esta (la llave sigue en la ventana)
      cambiarEstado(Estado::REPOSO);
      return;
    }
    int distancia = (vacioIntentos + 1) / 2;
    int slot = vacioBase + (vacioIntentos % 2 ? distancia : -distancia);
    slot = ((slot % SLOTS) + SLOTS) % SLOTS;
    if (slot == SLOT_HOME) {
      probarSiguienteVacio();
      return;
    }
    discoIrAVacio(slot);
    cambiarEstado(Estado::BUSCANDO_VACIO);
  }

  void guardarDevolucionSinConexion() {
    time_t ahora = time(nullptr);  // la hora la tomo de internet al conectarse (si ya la tenia)
    DevolucionGuardada devolucion{candidato, slotDevolucion, ahora > 1700000000 ? (uint32_t)ahora : 0};
    if (!memoriaAgregarDevolucion(devolucion)) {
      lcdMensaje("Memoria llena", "Retire la llave");
      cambiarEstado(Estado::SACAR_LLAVE);
      return;
    }
    Serial.printf("[estado] Devolucion guardada sin conexion: %s en el slot %d (%d guardadas)\n",
                  candidato.c_str(), slotDevolucion, memoriaDevolucionesGuardadas());
    aviso("Sin conexion", "Devol. guardada", 2 * MENSAJE_MS);
    vacioBase = slotDevolucion;
    vacioIntentos = 0;
    probarSiguienteVacio();
  }

  // US-10
  void empezarModoAlta() {
    candidato = "";
    tagAlta = "";
    actividadAlta = millis();
    avisoHasta = 0;
    lcdMensaje("Modo alta", "Acerque el tag");
    cambiarEstado(Estado::MODO_ALTA);
  }

  void salirModoAlta() {
    // El tag nuevo pudo quedar colgado en la ventana: el servidor dice otro lugar vacio
    inicioPendiente = true;
    irAlReposoTrasInicio = true;
    cambiarEstado(Estado::REPOSO);
  }

  void alRespuestaDevolucion(bool ok, const String &motivo, JsonDocument &resp) {
    if (!ok) {
      Serial.printf("[estado] Devolucion rechazada: %s\n", motivo.c_str());
      if (motivo == "CONFIRMAR_TERCERO") {  // US-20: la tenia otro docente
        String retiradaPor = resp["retiradaPor"] | "otro";
        lcdMensaje("Retirada por", retiradaPor.substring(0, 9) + " #=OK");
        cambiarEstado(Estado::CONFIRMAR_TERCERO);
        return;
      }
      if (motivo == "CREDENCIAL_NO_RECONOCIDA") {
        lcdMensaje("DNI desconocido", "Retire la llave");
      } else if (motivo == "ERROR_INTERNO") {
        lcdMensaje("Error servidor", "Retire la llave");
      } else {
        lcdMensaje("Llave no", "reconocida");
      }
      cambiarEstado(Estado::SACAR_LLAVE);
      return;
    }
    String aula = resp["aula"].as<String>();
    aviso("Llave de aula", aula + " recibida");
    slotReposo = resp["slotReposo"].isNull() ? -1 : resp["slotReposo"].as<int>();
    Serial.printf("[estado] Devolucion de la %s; slotReposo %d\n", aula.c_str(), slotReposo);
    volverAlReposo();
  }

  void alResponder(const String &tipo, JsonDocument &resp) {
    bool ok = resp["ok"] | false;
    String motivo = resp["motivo"] | "";
    if (tipo == "solicitud_retiro") {
      if (estado == Estado::ESPERANDO_SERVIDOR) alRespuestaRetiro(ok, motivo, resp);
      return;
    }
    if (tipo == "retiro_confirmado") {
      if (estado == Estado::ESPERANDO_SERVIDOR) alRespuestaRetiroConfirmado(ok, motivo);
      return;
    }
    if (tipo == "devolucion" && mandandoGuardada) {
      // US-14: una devolucion hecha sin conexion. Aceptada o no, sale de la cola (si no, se
      // reintentaria para siempre); el disco no se mueve
      mandandoGuardada = false;
      memoriaQuitarPrimeraDevolucion();
      Serial.printf("[estado] Devolucion guardada enviada: %s\n", ok ? "registrada" : motivo.c_str());
      return;
    }
    if (tipo == "devolucion") {
      if (estado == Estado::ESPERANDO_SERVIDOR) alRespuestaDevolucion(ok, motivo, resp);
      return;
    }
    if (tipo == "retiro_interrumpido") {  // US-15: el servidor ya cancelo la reserva
      memoriaBorrarRetiro();
      retiroInterrumpido = "";
      return;
    }
    if (tipo == "tag_leido") {  // US-10
      if (estado != Estado::MODO_ALTA) return;
      String aula = resp["aula"] | "";
      lcdMensaje("Tag " + tagAlta, aula.length() ? "Ya es aula " + aula : "Cargue en la web");
      return;
    }
    if (!ok) {
      Serial.printf("[estado] El servidor rechazo %s: %s\n", tipo.c_str(), motivo.c_str());
      return;
    }
    if (tipo == "inicio") {
      slotReposo = resp["slotReposo"].isNull() ? -1 : resp["slotReposo"].as<int>();
      Serial.printf("[estado] slotReposo: %d\n", slotReposo);
      if (irAlReposoTrasInicio && estado == Estado::REPOSO) {
        irAlReposoTrasInicio = false;
        if (slotReposo >= 0) {  // -1: el disco esta lleno, se queda en el HOME
          lcdMensaje("LlavesUBA", "Espere...");
          discoIrAVacio(slotReposo);
          cambiarEstado(Estado::IR_A_REPOSO);
        }
      }
    }
  }

  // --- Teclado ---

  void alTecla(char t) {
    Serial.printf("[teclado] %c\n", t);
    unsigned long ahora = millis();
    switch (estado) {
      case Estado::REPOSO:
        if (t != 'A' && t != 'B') return;
        if (t == 'B' && !redConectado()) {
          empezarDevolucion(true);  // US-14: se guarda y se manda al volver la conexion
        } else if (!redConectado()) {
          aviso("Sin conexion", redCausaSinConexion());  // sin conexion no se entregan llaves
        } else if (protocoloEsperando()) {  // todavia no contesto el evento anterior
          aviso("Espere...", "");
        } else if (t == 'A') {
          empezarIngreso();
        } else {
          empezarDevolucion(false);
        }
        return;

      case Estado::INGRESO_CODIGO:
      case Estado::INGRESO_AULA:
        ultimaTecla = ahora;
        if (t >= '0' && t <= '9') {
          if ((int)codigoEscrito.length() < (estado == Estado::INGRESO_AULA ? 6 : DNI_MAX_DIGITOS)) codigoEscrito += t;
          mostrarCodigo();
        } else if (t == '*') {
          if (codigoEscrito.length()) codigoEscrito.remove(codigoEscrito.length() - 1);
          mostrarCodigo();
        } else if (t == '#') {
          confirmarCodigo();
        } else if (t == 'C') {
          cambiarEstado(Estado::REPOSO);
        }
        return;

      case Estado::ESPERANDO_SERVIDOR:
        // Solo se puede abandonar la espera del codigo: el retiro y la devolucion ya pasaron
        // (la llave se movio) y hay que registrarlos si o si
        if (t == 'C' && protocoloTipoPendiente() == "solicitud_retiro" && retiro.intento == 1) {
          protocoloCancelar();
          cambiarEstado(Estado::REPOSO);
        }
        return;

      case Estado::ESPERANDO_RETIRO:
        if (t == 'C') terminarPorTiempo();  // el docente no la quiere: igual que si no la sacara
        return;

      case Estado::ESPERANDO_DEVOLUCION:
        if (t == 'C') {
          cambiarEstado(Estado::REPOSO);
        } else if (devolucionSinConexion) {
          return;  // sin conexion no se puede verificar un DNI
        } else if (t >= '0' && t <= '9' && (int)dniDevolucion.length() < DNI_MAX_DIGITOS) {
          dniDevolucion += t;  // US-20
          dniConfirmado = false;
          mostrarDevolucion();
        } else if (t == '*' && dniDevolucion.length()) {
          dniDevolucion.remove(dniDevolucion.length() - 1);
          dniConfirmado = false;
          mostrarDevolucion();
        } else if (t == '#') {
          int largo = dniDevolucion.length();
          if (largo >= DNI_MIN_DIGITOS && largo <= DNI_MAX_DIGITOS) {
            dniConfirmado = true;
            mostrarDevolucion();
          } else {
            lcdMensaje("Cuelgue la llave", "DNI: 7 u 8 nros");
          }
        }
        return;

      case Estado::CONFIRMAR_TERCERO:  // US-20
        if (t == '#') {
          mandarDevolucion(true);
        } else if (t == 'C') {
          lcdMensaje("No se registro", "Retire la llave");
          cambiarEstado(Estado::SACAR_LLAVE);
        }
        return;

      case Estado::MODO_ALTA:  // US-10
        if (t == 'C') salirModoAlta();
        return;

      default:
        return;  // girando, bloqueado o con error: el teclado no hace nada
    }
  }

  // --- La maquina de estados ---

  void actualizarEstado() {
    unsigned long ahora = millis();
    ResultadoDisco r = discoResultado();
    switch (estado) {
      case Estado::HOMING:
        if (r == ResultadoDisco::EN_CURSO) break;
        if (r == ResultadoDisco::OK) {
          Serial.printf("[estado] Homing OK: %.0f ms por slot\n", discoMsPorSlot());
          inicioPendiente = true;
          irAlReposoTrasInicio = true;
          cambiarEstado(Estado::REPOSO);
        } else {
          fallar("Error del disco", "Avisar porteria", "MOTOR_NO_GIRA",
                 "el homing no encontro el tag HOME");
        }
        break;

      case Estado::IR_A_REPOSO:
        if (r == ResultadoDisco::EN_CURSO) break;
        if (r != ResultadoDisco::OK) {
          // El lugar no estaba vacio: queda donde esta. En la devolucion se va a notar.
          Serial.printf("[estado] Slot de reposo %d: %s\n", slotReposo, discoTextoResultado(r));
        }
        if (primerReposo) {  // US-15: despues de prender (o de un corte de luz)
          primerReposo = false;
          aviso("Equipo listo", "");
        }
        cambiarEstado(Estado::REPOSO);
        break;

      case Estado::REPOSO:
        if (protocoloPidioRecalibrar()) {
          empezarHoming();
          break;
        }
        if (protocoloPidioModoAlta()) {
          empezarModoAlta();
          break;
        }
        // Entrega directa: el docente apreto "Pedir llave" en la web (05/11/2026)
        if (entregaPendiente.length() && redConectado() && !protocoloEsperando()) {
          retiro = Retiro();
          retiro.codigo = entregaPendiente;
          retiro.desdeWeb = true;
          entregaPendiente = "";
          lcdMensaje("Pedido de la web", "Espere...");
          mandarSolicitudRetiro();
          break;
        }
        mostrarReposo();
        break;

      case Estado::INGRESO_CODIGO:
      case Estado::INGRESO_AULA:
        if (ahora - ultimaTecla >= CODIGO_INACTIVIDAD_MS) cambiarEstado(Estado::REPOSO);
        break;

      case Estado::ESPERANDO_SERVIDOR:
        // Sin respuesta: el modulo protocolo reenvia el evento solo (mismo eventId)
        if (protocoloIntentos() >= 2) lcdMensaje("Sin respuesta", "Reintentando...");
        break;

      case Estado::MOVIENDO:
        if (r == ResultadoDisco::EN_CURSO) break;
        if (r == ResultadoDisco::OK) {
          lcdMensaje("Aula " + retiro.aula + " servida", "RETIRE SU LLAVE");
          retiro.ausenteDesde = 0;
          cambiarEstado(Estado::ESPERANDO_RETIRO);
        } else if (retiro.intento == 1) {
          // US-05: no estaba en su lugar ni en los vecinos ni en una vuelta entera
          Serial.println("[estado] La llave no aparecio: homing y otra busqueda (intento 2)");
          retiro.intento = 2;
          lcdMensaje("Reposicionando", "Espere...");
          discoHoming();
          cambiarEstado(Estado::REPOSICIONANDO);
        } else {
          llaveNoEncontrada();
        }
        break;

      case Estado::REPOSICIONANDO:
        if (r == ResultadoDisco::EN_CURSO) break;
        if (r == ResultadoDisco::OK) {
          // El homing puede tardar mas de un minuto: se vuelve a pedir la llave, asi el servidor
          // extiende la reserva y dice donde esta ahora
          mandarSolicitudRetiro();
        } else {
          memoriaBorrarRetiro();  // US-15: el retiro termino (sin llave)
          fallar("Error del disco", "Avisar porteria", "MOTOR_NO_GIRA",
                 "el homing no encontro el tag HOME (retiro)", retiro.codigo);
        }
        break;

      case Estado::ESPERANDO_RETIRO:
        if (discoTagPresente(retiro.uid)) {
          retiro.ausenteDesde = 0;
        } else if (!retiro.ausenteDesde) {
          retiro.ausenteDesde = ahora;
        } else if (ahora - retiro.ausenteDesde >= RETIRO_ESTABLE_MS) {
          // El docente se llevo la llave
          JsonDocument evento;
          evento["codigo"] = retiro.codigo;
          evento["uid"] = retiro.uid;
          evento["slot"] = discoSlot();  // donde estaba realmente
          protocoloEnviar("retiro_confirmado", evento);
          lcdMensaje("Registrando", "el retiro...");
          cambiarEstado(Estado::ESPERANDO_SERVIDOR);
          break;
        }
        // Si la llave ya no se ve, se la estan llevando: primero se confirma el retiro. Si no, una
        // llave sacada en el ultimo segundo y medio quedaria como "nadie la retiro".
        if (ahora - desdeEstado >= RETIRO_TIMEOUT_MS && !retiro.ausenteDesde) terminarPorTiempo();
        break;

      case Estado::ESPERANDO_DEVOLUCION: {
        String tag = discoTagEnVentana();
        if (!tag.length() || tag == UID_HOME) {
          candidato = "";
        } else if (tag != candidato) {
          candidato = tag;
          candidatoDesde = ahora;
        } else if (ahora - candidatoDesde >= DEVOLUCION_ESTABLE_MS) {
          slotDevolucion = discoSlot();
          if (devolucionSinConexion || !redConectado()) {
            guardarDevolucionSinConexion();  // US-14
            break;
          }
          // US-20: escribio un DNI y falta el #. Si en un minuto no lo confirma, se registra como una
          // devolucion comun (si no, el equipo quedaria esperando y nadie podria retirar)
          if (dniDevolucion.length() && !dniConfirmado && ahora - desdeEstado < DEVOLUCION_ESPERA_MS) break;
          mandarDevolucion(false);
          break;
        }
        if (!candidato.length() && ahora - desdeEstado >= DEVOLUCION_ESPERA_MS) {
          cambiarEstado(Estado::REPOSO);
        }
        break;
      }

      case Estado::SACAR_LLAVE:
        // Esperar que se lleven la llave rechazada (o un rato, por si la dejan colgada)
        if ((!discoTagPresente(candidato) && ahora - desdeEstado >= MENSAJE_MS) ||
            ahora - desdeEstado >= DEVOLUCION_ESPERA_MS) {
          cambiarEstado(Estado::REPOSO);
        }
        break;

      case Estado::CONFIRMAR_TERCERO:  // US-20: sin confirmar, no se registra
        if (ahora - desdeEstado >= CONFIRMAR_TERCERO_MS) {
          lcdMensaje("No se registro", "Retire la llave");
          cambiarEstado(Estado::SACAR_LLAVE);
        }
        break;

      case Estado::BUSCANDO_VACIO:  // US-14
        if (r == ResultadoDisco::EN_CURSO) break;
        if (r == ResultadoDisco::OK) {
          slotReposo = discoSlot();
          cambiarEstado(Estado::REPOSO);
        } else {
          probarSiguienteVacio();
        }
        break;

      case Estado::MODO_ALTA: {  // US-10
        String tag = discoTagEnVentana();
        if (!tag.length() || tag == UID_HOME) {
          candidato = "";
          if (!tag.length()) tagAlta = "";  // lo sacaron: se puede volver a leer
        } else if (tag != candidato) {
          candidato = tag;
          candidatoDesde = ahora;
        } else if (tag != tagAlta && ahora - candidatoDesde >= DEVOLUCION_ESTABLE_MS && !protocoloEsperando()) {
          tagAlta = tag;
          actividadAlta = ahora;
          JsonDocument evento;
          evento["uid"] = tag;
          evento["slot"] = discoSlot();
          protocoloEnviar("tag_leido", evento);
          lcdMensaje("Leyendo tag", tag);
        }
        if (ahora - actividadAlta >= MODO_ALTA_MS) salirModoAlta();
        break;
      }

      case Estado::BLOQUEADO: {
        unsigned long pasaron = ahora - desdeEstado;
        if (pasaron >= BLOQUEO_TECLADO_MS) {
          cambiarEstado(Estado::REPOSO);
        } else {
          unsigned long faltan = (BLOQUEO_TECLADO_MS - pasaron + 999) / 1000;
          lcdMensaje(String(CODIGOS_MAL_MAX) + " codigos mal", "Espere " + String(faltan) + " s");
        }
        break;
      }

      case Estado::ERROR:
        // El LCD ya dice el error. El preceptor puede pedir recalibrar desde el servidor.
        if (protocoloPidioRecalibrar() && lectorOk) empezarHoming();
        break;
    }
  }

  void comandoSerie(String linea) {
    linea.trim();
    if (linea == "r") {
      redImprimirEstado();
      Serial.print("  Faltan:");
      for (const String &aula : protocoloFaltantes()) Serial.printf(" %s", aula.c_str());
      Serial.printf("\n  Estado: %s, slotReposo %d\n", nombre(estado), slotReposo);
    } else if (linea == "p") {
      String tag = discoTagEnVentana();
      Serial.printf("  Disco en el slot %d (%.2f). En la ventana: %s\n", discoSlot(),
                    discoPosicion(), tag.length() ? tag.c_str() : "nada");
    } else if (linea == "h") {
      if (lectorOk && (estado == Estado::REPOSO || estado == Estado::ERROR)) {
        empezarHoming();
      } else {
        Serial.println("  Ahora no se puede (el disco esta ocupado o falla el lector)");
      }
    } else if (linea == "ledinfo") {
      ledImprimirEstado();
    } else if (linea == "led" || linea.startsWith("led ")) {
      // "led" naranja, "led rojo", "led verde", "led 1 3" naranja con 1 ms verde y 3 ms rojo
      String resto = linea.substring(3);
      resto.trim();
      pruebaLedColor = ColorLed::NARANJA;
      if (resto == "rojo") {
        pruebaLedColor = ColorLed::ROJO;
      } else if (resto == "verde") {
        pruebaLedColor = ColorLed::VERDE;
      } else if (resto.length()) {
        int espacio = resto.indexOf(' ');
        int v = resto.substring(0, espacio).toInt(), r = resto.substring(espacio + 1).toInt();
        ledRepartoNaranja(v, r);
        Serial.printf("  Naranja: %d ms verde, %d ms rojo\n", v, r);
      }
      pruebaLedHasta = millis() + 60000;
      Serial.printf("  LED de prueba durante 60 s: %s\n", resto.length() ? resto.c_str() : "naranja");
    } else if (linea == "trazas") {
      trazas = !trazas;
      discoTrazas(trazas);
      Serial.printf("  Trazas del lector: %s\n", trazas ? "prendidas" : "apagadas");
    } else if (linea.startsWith("t ")) {
      for (unsigned i = 2; i < linea.length(); i++) alTecla(linea[i]);
    } else if (linea.length()) {
      Serial.println("  Comandos: r (red), p (disco), h (homing), t TECLAS (ej. t A123456#), trazas, led [rojo|verde|V R], ledinfo");
    }
  }

  void leerSerie() {
    static String linea;
    while (Serial.available()) {
      char c = Serial.read();
      if (c == '\n' || c == '\r') {
        comandoSerie(linea);
        linea = "";
      } else {
        linea += c;
      }
    }
  }

  // Unos 300 ms mirando si la D esta apretada (el teclado tiene antirrebote)
  bool teclaDAlEncender() {
    unsigned long inicio = millis();
    while (millis() - inicio < 300) {
      if (teclaApretada('D')) return true;
      delay(10);
    }
    return false;
  }
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);

  ledIniciar();
  motorIniciar();
  lcdIniciar();
  lcdMensaje("LlavesUBA", "Iniciando...");
  lectorOk = rfidIniciar();
  discoIniciar();
  // Unas lecturas antes de girar: si el HOME ya esta en la ventana, el homing lo sabe
  if (lectorOk) {
    for (int i = 0; i < 5; i++) discoActualizar();
  }

  modoDiagnostico = teclaDAlEncender();
  if (modoDiagnostico) {
    diagnosticoIniciar(lectorOk);
    return;
  }

  Serial.println("\nLlavesUBA: firmware, paso 2b (retiro y devolucion)");
  discoTrazas(trazas);
  redIniciar(protocoloAlMensaje);
  protocoloIniciar();
  memoriaIniciar();
  retiroInterrumpido = memoriaRetiroInterrumpido();  // US-15
  if (retiroInterrumpido.length()) {
    Serial.printf("[estado] Se corto la luz durante el retiro %s: se avisa al servidor\n",
                  retiroInterrumpido.c_str());
  }
  int guardadas = memoriaDevolucionesGuardadas();  // US-14
  if (guardadas) Serial.printf("[estado] %d devoluciones guardadas sin conexion\n", guardadas);
  if (lectorOk) {
    empezarHoming();
  } else {
    fallar("Error: lector", "Revisar cables", "LECTOR_NO_RESPONDE", "el RC522 no responde");
  }
}

void loop() {
  if (modoDiagnostico) {
    diagnosticoLoop();
    return;
  }

  if (lectorOk) discoActualizar();
  // Reconectar al broker traba unos segundos: solo con el disco quieto
  redActualizar(discoResultado() != ResultadoDisco::EN_CURSO);
  protocoloActualizar();

  if (redConexiones() != ultimaConexion) {  // se (re)conecto al broker: avisar como esta el disco
    ultimaConexion = redConexiones();
    if (discoListo()) inicioPendiente = true;
  }
  JsonDocument resp;
  if (protocoloRespuesta(resp)) alResponder(protocoloTipoPendiente(), resp);
  mandarPendientes();

  actualizarEstado();
  actualizarLed();
  ledActualizar();

  // Un pedido de la web llega en cualquier momento: espera hasta que el equipo este en reposo
  String pedida = protocoloEntregaPedida();
  if (pedida.length() && estado == Estado::ERROR) {
    // Trabado por una falla: no puede entregar (el servidor ya no deberia pedirlo, ver
    // equipo_con_falla en el backend). Mismo motivo que en fallar(): no se guarda
    Serial.println("[estado] Pedido de la web ignorado: el equipo esta en error");
  } else if (pedida.length()) {
    entregaPendiente = pedida;
    // El modo alta (US-10) puede durar minutos: un docente esperando frente al equipo tiene
    // prioridad, asi que se termina y el pedido se atiende apenas el disco queda en reposo
    if (estado == Estado::MODO_ALTA) {
      Serial.println("[estado] Pedido de la web: termina el modo alta");
      salirModoAlta();
    }
  }

  char t = teclaLeer();
  if (t) alTecla(t);
  leerSerie();
}
