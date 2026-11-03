#include "red.h"

#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <time.h>

#include "config.h"
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
