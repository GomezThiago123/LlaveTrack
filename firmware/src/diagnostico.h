// Modo diagnostico (tecla D apretada al encender): el disco sin red, comandos por Monitor Serie.
#pragma once

// El hardware ya tiene que estar iniciado (lo hace main). lector: si el RC522 respondio.
void diagnosticoIniciar(bool lector);
void diagnosticoLoop();
