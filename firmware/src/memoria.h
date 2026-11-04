// Lo que el equipo tiene que recordar aunque se corte la luz (memoria flash, con Preferences):
//   - US-15: el retiro que estaba entregando. Al volver la luz se avisa al servidor, que cancela
//     la reserva (asi no queda a nombre del docente una llave que nunca recibio).
//   - US-14: las devoluciones hechas sin conexion, con su hora, para mandarlas al volver.
#pragma once
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
