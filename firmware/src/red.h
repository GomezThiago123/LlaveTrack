// WiFi + MQTT con reconexion, y la hora por NTP.
//
// Todo sin bloquear, salvo conectarse al broker (hasta MQTT_TIMEOUT_S): eso solo se intenta
// cuando el programa avisa que puede esperar (el disco esta quieto).
//
// Topicos (docs/protocolo-mqtt.md), con el prefijo llavetrack/v1/{DEVICE_ID}/:
//   publica   estado (retenido, con LWT), latido, evt/{tipo}
//   recibe    resp, cmd, faltantes y llavetrack/v1/servidor/estado
#pragma once
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
