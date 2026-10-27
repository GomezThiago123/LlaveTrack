// Teclado 4x4. Teclas: A retirar, B devolver, C cancelar, * borrar, # confirmar, D diagnostico.
#pragma once

// La tecla que se acaba de apretar, o 0 si no hay ninguna
char teclaLeer();
// true si la tecla esta apretada ahora (para el modo diagnostico al encender)
bool teclaApretada(char tecla);
