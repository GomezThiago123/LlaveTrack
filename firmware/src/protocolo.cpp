#include "protocolo.h"

#include "config.h"
#include "red.h"
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
