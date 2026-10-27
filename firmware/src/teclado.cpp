#include "teclado.h"

#include <Keypad.h>

#include "config.h"

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
