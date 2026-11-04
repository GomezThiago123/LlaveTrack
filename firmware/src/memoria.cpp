#include "memoria.h"

#include <Preferences.h>

#include <vector>

#include "config.h"

namespace {
Preferences memoria;  // espacio "llavetrack" en la flash

// La cola se guarda como un solo texto: "uid,slot,hora;uid,slot,hora"
std::vector<DevolucionGuardada> leerCola() {
  std::vector<DevolucionGuardada> cola;
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
  memoria.putString("devol", texto);
}
}  // namespace

void memoriaIniciar() { memoria.begin("llavetrack", false); }

void memoriaGuardarRetiro(const String &codigo) { memoria.putString("retiro", codigo); }
void memoriaBorrarRetiro() { memoria.remove("retiro"); }
String memoriaRetiroInterrumpido() { return memoria.getString("retiro", ""); }

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
