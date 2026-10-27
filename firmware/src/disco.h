// Donde esta el disco y como moverlo.
//
// El motor es de continua: no sabe cuanto giro. La posicion se estima por TIEMPO (milisegundos
// por slot, medidos al arrancar entre dos pasadas por el tag HOME) y se corrige cada vez que el
// lector ve el HOME. Para entregar una llave no hace falta precision: el disco gira hasta que el
// lector ve ESE UID y se centra en el.
//
// Todo es "no bloqueante": se arranca una tarea y discoActualizar() (en cada vuelta del loop)
// la va avanzando. Mientras, el resto del programa sigue andando (teclado, red, LCD).
#pragma once
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

ResultadoDisco discoResultado();
const char *discoTextoResultado(ResultadoDisco resultado);
bool discoListo();         // ya hizo el homing: sabe donde esta
int discoSlot();           // slot frente a la ventana (redondeado)
float discoPosicion();     // con decimales
float discoMsPorSlot();
bool discoTagPresente(const String &uid);  // ese tag esta frente al lector ahora
bool discoHayTag();                        // hay algun tag frente al lector
String discoTagEnVentana();                // el ultimo tag leido que sigue presente ("" si no hay)
