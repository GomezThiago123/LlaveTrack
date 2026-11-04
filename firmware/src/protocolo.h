// Los mensajes JSON con el servidor (docs/protocolo-mqtt.md).
//
// Eventos: se manda uno a la vez y se reenvia con el MISMO eventId cada RESPUESTA_TIMEOUT_MS (y
// al reconectar) hasta que llega su respuesta. PubSubClient publica con QoS 0, asi que la
// confiabilidad es esta: el servidor descarta los repetidos y vuelve a mandar la respuesta.
#pragma once
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
