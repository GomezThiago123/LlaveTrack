// Datos de la red y del broker. Copiar este archivo como secrets.h (en esta misma carpeta) y
// completarlo. secrets.h NO va al repo (esta en el .gitignore): tiene claves.
#pragma once

// Nombre del equipo: tiene que coincidir con el deviceId del seed (backend/seed/datos.json).
// "servidor" esta reservado.
constexpr const char *DEVICE_ID = "equipo-01";

// --- WiFi ---
// false = red comun con clave (casa, hotspot del celular)
// true  = WPA2-Enterprise (PEAP) de la escuela: usuario y clave de una cuenta
constexpr bool WIFI_ENTERPRISE = false;
constexpr const char *WIFI_SSID = "nombre-de-la-red";
constexpr const char *WIFI_CLAVE = "clave-de-la-red";
constexpr const char *WIFI_USUARIO = "";  // solo para Enterprise
// Solo para Enterprise, si la red pide verificar su certificado (PEM). Vacio = no se verifica.
constexpr const char *WIFI_CA_PEM = "";

// --- Broker MQTT ---
// En desarrollo: la IP de la compu donde corre Mosquitto (en Linux: `hostname -I`;
// en Windows: `ipconfig`). Mejor una IP que un nombre: resolver un nombre puede trabar unos segundos.
constexpr const char *MQTT_HOST = "192.168.0.10";
constexpr int MQTT_PUERTO = 1883;     // 8883 con TLS
constexpr const char *MQTT_USUARIO = "";  // vacio = anonimo (solo en desarrollo)
constexpr const char *MQTT_CLAVE = "";
// TLS (para la demo, con el broker en la nube)
constexpr bool MQTT_TLS = false;
// Certificado de la autoridad que firmo el del broker (PEM). Con TLS y esto vacio, la conexion
// va cifrada pero sin verificar con quien se habla: solo para probar.
constexpr const char *MQTT_CA_PEM = "";
