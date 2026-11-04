// Firmware del equipo LlaveTrack: la maquina de estados (ver CLAUDE.md, seccion Firmware).
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
// "t A123456#" simula esas teclas (para probar sin tocar el teclado).

#include <Arduino.h>
#include <ArduinoJson.h>

#include <vector>

#include "config.h"
#include "diagnostico.h"
#include "disco.h"
#include "lcd.h"
#include "led.h"
#include "motor.h"
#include "protocolo.h"
#include "red.h"
#include "rfid.h"
#include "teclado.h"

namespace {
enum class Estado {
  HOMING,                // buscando el HOME (al prender o con el comando recalibrar)
  IR_A_REPOSO,           // llevando un lugar vacio a la ventana
  REPOSO,
  INGRESO_CODIGO,        // tecla A: el docente escribe el codigo
  ESPERANDO_SERVIDOR,    // se mando un evento (codigo, retiro o devolucion) y falta la respuesta
  MOVIENDO,              // el disco busca la llave pedida
  REPOSICIONANDO,        // US-05, intento 2: homing de nuevo antes de volver a buscarla
  ESPERANDO_RETIRO,      // la llave esta en la ventana: el docente la tiene que sacar
  ESPERANDO_DEVOLUCION,  // tecla B: el docente tiene que colgar la llave en la ventana
  SACAR_LLAVE,           // devolucion rechazada: esperando que saquen esa llave de la ventana
  BLOQUEADO,             // muchos codigos mal seguidos: el teclado no responde un rato
  ERROR,                 // el disco no anda: no se entrega nada (el LCD dice por que)
};
Estado estado = Estado::HOMING;
unsigned long desdeEstado = 0;  // millis() al entrar al estado actual
bool modoDiagnostico = false;
bool lectorOk = false;

// `inicio` se manda despues de cada homing y en cada reconexion al broker
bool inicioPendiente = false;
unsigned ultimaConexion = 0;        // redConexiones() la ultima vez que se miro
bool irAlReposoTrasInicio = false;  // despues del homing: el disco quedo en el HOME
int slotReposo = -1;                // el lugar vacio frente a la ventana (-1: no se sabe)

// Falla para avisarle al servidor (crea un incidente que ve el preceptor, US-05)
String errorParaMandar, detalleError, codigoError;

// Un aviso ("Gracias", "Codigo invalido") queda en el LCD hasta este momento
unsigned long avisoHasta = 0;

// El retiro en curso
struct Retiro {
  String codigo, uid, aula, apellido;
  int slot = -1;     // donde dice el servidor que esta la llave
  int intento = 1;   // US-05: el 2do es despues de repetir el homing
  unsigned long ausenteDesde = 0;  // desde cuando el lector no ve la llave (0: la ve)
};
Retiro retiro;
String codigoEscrito;          // lo que va escribiendo el docente
unsigned long ultimaTecla = 0;
int codigosMal = 0;            // rechazados seguidos (se bloquea el teclado al llegar al maximo)

// La devolucion en curso: el tag que aparecio en la ventana y se esta viendo si queda estable.
// Tambien vale si la llave ya estaba colgada al apretar B (algunos cuelgan primero).
String candidato;
unsigned long candidatoDesde = 0;

const char *nombre(Estado e) {
  switch (e) {
    case Estado::HOMING: return "HOMING";
    case Estado::IR_A_REPOSO: return "IR_A_REPOSO";
    case Estado::REPOSO: return "REPOSO";
    case Estado::INGRESO_CODIGO: return "INGRESO_CODIGO";
    case Estado::ESPERANDO_SERVIDOR: return "ESPERANDO_SERVIDOR";
    case Estado::MOVIENDO: return "MOVIENDO";
    case Estado::REPOSICIONANDO: return "REPOSICIONANDO";
    case Estado::ESPERANDO_RETIRO: return "ESPERANDO_RETIRO";
    case Estado::ESPERANDO_DEVOLUCION: return "ESPERANDO_DEVOLUCION";
    case Estado::SACAR_LLAVE: return "SACAR_LLAVE";
    case Estado::BLOQUEADO: return "BLOQUEADO";
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
  auto pantallas = pantallasReposo(hora.length() ? hora : "LlaveTrack", protocoloFaltantes());
  lcdMensaje(pantallas[(millis() / LCD_ROTACION_MS) % pantallas.size()], "A:Retirar B:Dev.");
}

// LED: verde = conectado y no falta ninguna llave; naranja = falta alguna; rojo titilando =
// sin conexion (WiFi, broker o servidor)
void actualizarLed() {
  if (!redConectado()) {
    ledColor(ColorLed::ROJO_TITILANDO);
  } else {
    ledColor(protocoloFaltantes().empty() ? ColorLed::VERDE : ColorLed::NARANJA);
  }
}

// --- Eventos al servidor (de a uno: se espera la respuesta antes de mandar otro) ---

void mandarPendientes() {
  if (!redConectado() || protocoloEsperando()) return;
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
  evento["codigo"] = retiro.codigo;
  protocoloEnviar("solicitud_retiro", evento);
  cambiarEstado(Estado::ESPERANDO_SERVIDOR);
}

// --- Retiro (US-04 y US-05) ---

void mostrarCodigo() {
  String linea2 = codigoEscrito;
  while ((int)linea2.length() < CODIGO_DIGITOS) linea2 += "_";
  lcdMensaje("Ingrese codigo", linea2 + "  #=OK");
}

void empezarIngreso() {
  codigoEscrito = "";
  ultimaTecla = millis();
  avisoHasta = 0;
  mostrarCodigo();
  cambiarEstado(Estado::INGRESO_CODIGO);
}

void confirmarCodigo() {
  if ((int)codigoEscrito.length() != CODIGO_DIGITOS) {
    lcdMensaje("Son 6 numeros", codigoEscrito);
    return;
  }
  if (!redConectado()) {
    aviso("Sin conexion", redCausaSinConexion());
    cambiarEstado(Estado::REPOSO);
    return;
  }
  retiro = Retiro();
  retiro.codigo = codigoEscrito;
  lcdMensaje("Verificando", "el codigo...");
  mandarSolicitudRetiro();
}

void codigoRechazado(const String &motivo) {
  if (motivo == "ERROR_INTERNO") {  // no es culpa del docente: no cuenta para el bloqueo
    aviso("Error del", "servidor");
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
  aviso(linea1, "Le quedan " + String(CODIGOS_MAL_MAX - codigosMal));
  volverAlReposo();
}

// La llave no aparecio en los dos intentos: no se entrega nada (US-05)
void llaveNoEncontrada() {
  aviso("Pedi la llave", "en porteria", 3 * MENSAJE_MS);
  errorParaMandar = "LLAVE_NO_ENCONTRADA";
  detalleError = "uid " + retiro.uid + ", slot " + String(retiro.slot);
  codigoError = retiro.codigo;
  volverAlReposo();
}

void terminarPorTiempo() {
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
  retiro.uid = resp["uid"].as<String>();
  retiro.slot = resp["slot"] | -1;
  retiro.aula = resp["aula"].as<String>();
  retiro.apellido = resp["apellido"].as<String>();
  Serial.printf("[estado] Retiro: aula %s, uid %s, slot %d (intento %d)\n", retiro.aula.c_str(),
                retiro.uid.c_str(), retiro.slot, retiro.intento);
  if (retiro.intento == 1) lcdMensaje("Buscando llave", "Aula " + retiro.aula);
  discoBuscar(retiro.uid, retiro.slot);
  cambiarEstado(Estado::MOVIENDO);
}

void alRespuestaRetiroConfirmado(bool ok, const String &motivo) {
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

void empezarDevolucion() {
  candidato = "";
  avisoHasta = 0;
  lcdMensaje("Cuelgue la", "llave");
  cambiarEstado(Estado::ESPERANDO_DEVOLUCION);
}

void alRespuestaDevolucion(bool ok, const String &motivo, JsonDocument &resp) {
  if (!ok) {
    Serial.printf("[estado] Devolucion rechazada: %s\n", motivo.c_str());
    if (motivo == "ERROR_INTERNO") {
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
  if (tipo == "devolucion") {
    if (estado == Estado::ESPERANDO_SERVIDOR) alRespuestaDevolucion(ok, motivo, resp);
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
        lcdMensaje("LlaveTrack", "Espere...");
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
      if (!redConectado()) {
        aviso("Sin conexion", redCausaSinConexion());
      } else if (protocoloEsperando()) {  // todavia no contesto el evento anterior
        aviso("Espere...", "");
      } else if (t == 'A') {
        empezarIngreso();
      } else {
        empezarDevolucion();
      }
      return;

    case Estado::INGRESO_CODIGO:
      ultimaTecla = ahora;
      if (t >= '0' && t <= '9') {
        if ((int)codigoEscrito.length() < CODIGO_DIGITOS) codigoEscrito += t;
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
      if (t == 'C') cambiarEstado(Estado::REPOSO);
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
      cambiarEstado(Estado::REPOSO);
      break;

    case Estado::REPOSO:
      if (protocoloPidioRecalibrar()) {
        empezarHoming();
        break;
      }
      mostrarReposo();
      break;

    case Estado::INGRESO_CODIGO:
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
        JsonDocument evento;
        evento["uid"] = candidato;
        evento["slot"] = discoSlot();
        protocoloEnviar("devolucion", evento);
        lcdMensaje("Verificando", "la llave...");
        cambiarEstado(Estado::ESPERANDO_SERVIDOR);
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
  } else if (linea.startsWith("t ")) {
    for (unsigned i = 2; i < linea.length(); i++) alTecla(linea[i]);
  } else if (linea.length()) {
    Serial.println("  Comandos: r (red), p (disco), h (homing), t TECLAS (ej. t A123456#)");
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
  lcdMensaje("LlaveTrack", "Iniciando...");
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

  Serial.println("\nLlaveTrack: firmware, paso 2b (retiro y devolucion)");
  redIniciar(protocoloAlMensaje);
  protocoloIniciar();
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

  char t = teclaLeer();
  if (t) alTecla(t);
  leerSerie();
}
