#include "disco.h"

#include <math.h>

#include "config.h"
#include "motor.h"
#include "rfid.h"

namespace {

// --- Tags frente al lector ---
// Cada tag que aparece se anota con cuando se vio por primera y por ultima vez. Si deja de
// verse TAG_AUSENTE_MS, "salio": con la primera y la ultima vez se calcula su centro.
struct TagVisto {
  String uid;
  unsigned long primera = 0, ultima = 0;
  float posPrimera = 0;  // donde estimabamos el disco cuando aparecio
  bool activo = false;
};
constexpr int MAX_TAGS = 6;
TagVisto vistos[MAX_TAGS];
String ultimoTag;

// --- Posicion ---
float pos = 0;        // slot frente a la ventana (0 a SLOTS), estimado
int dirSlots = 0;     // +1: pasan los slots 1, 2, 3...  -1: al reves  0: quieto
unsigned long tAnterior = 0;
float msPorSlot = (float)VUELTA_MS_INICIAL / SLOTS;
float anchoTag = 0.5;  // cuantos slots dura un tag frente al lector (se mide con el HOME)
bool listo = false;

// --- Tarea en curso ---
enum class Tarea { NADA, HOMING, MOVER, DIAGNOSTICO };
Tarea tarea = Tarea::NADA;
ResultadoDisco resultado = ResultadoDisco::OK;

// Homing: fase 0 = esperando el primer paso completo del HOME, 1 = el segundo
int faseHoming = 0;
bool homeAlEmpezar = false;  // si ya estaba frente al lector, ese paso no sirve (no se vio entrar)
unsigned long inicioHoming = 0, ultimoHomeMs = 0;
float centro1Ms = 0;

// Mover
enum class Modo { IR, BUSCAR, VACIO };
Modo modo = Modo::IR;
float objetivo = 0;
float restante = 0;  // slots que faltan recorrer en el sentido actual
bool vueltaCompleta = false;
String uidBuscado;
int slotEsperado = 0;
int faseBusqueda = 0;  // 0 el esperado, 1 el siguiente, 2 el anterior, 3 una vuelta entera
int empujones = 0;
bool llegando = false, verificando = false;
unsigned long tLlegada = 0, inicioVerificar = 0;
bool vioObjetivo = false, vioAlgo = false;

// Diagnostico
struct Marca {
  String uid;
  float desde, hasta;
};
constexpr int MAX_MARCAS = 40;
Marca marcas[MAX_MARCAS];
int cantMarcas = 0;
float recorrido = 0;

float normalizar(float slot) {
  float s = fmodf(slot, SLOTS);
  return s < 0 ? s + SLOTS : s;
}

// De `desde` a `hasta` por el camino mas corto, con signo (entre -SLOTS/2 y SLOTS/2)
float distanciaCorta(float desde, float hasta) {
  float d = normalizar(hasta - desde);
  return d > SLOTS / 2.0f ? d - SLOTS : d;
}

// Distancia hasta el objetivo yendo en el sentido actual (siempre positiva)
float distanciaEnSentido(float desde, float hasta, int sentido) {
  return sentido > 0 ? normalizar(hasta - desde) : normalizar(desde - hasta);
}

void girar(int sentidoSlots) {
  dirSlots = sentidoSlots;
  tAnterior = millis();
  // El sentido fisico del motor depende de para que lado esta numerado el disco
  bool adelante = (sentidoSlots > 0) == ADELANTE_SUMA_SLOTS;
  motorGirar(adelante ? 1 : -1);
}

void frenar() {
  dirSlots = 0;
  motorFrenar();
}

// Suma lo que giro desde la ultima vez. Devuelve cuantos slots avanzo.
float integrar() {
  unsigned long ahora = millis();
  float avance = 0;
  if (dirSlots != 0) {
    avance = (ahora - tAnterior) / msPorSlot;
    pos = normalizar(pos + dirSlots * avance);
  }
  tAnterior = ahora;
  return avance;
}

void terminar(ResultadoDisco r) {
  frenar();
  tarea = Tarea::NADA;
  resultado = r;
}

// --- Movimiento ---

void irHacia(float destino) {
  objetivo = normalizar(destino);
  vueltaCompleta = false;
  llegando = verificando = false;
  float d = distanciaCorta(pos, objetivo);
  restante = fabsf(d);
  if (restante < 0.05f) {  // ya estamos: directo a verificar
    verificando = true;
    inicioVerificar = millis();
    vioObjetivo = vioAlgo = false;
    return;
  }
  girar(d > 0 ? 1 : -1);
}

void darVuelta() {
  vueltaCompleta = true;
  llegando = verificando = false;
  restante = SLOTS;
  girar(1);
}

void empezarMover(Modo m, float destino) {
  tarea = Tarea::MOVER;
  resultado = ResultadoDisco::EN_CURSO;
  modo = m;
  faseBusqueda = 0;
  empujones = 0;
  irHacia(destino);
}

// Termino de mirar el lector en el slot al que llegamos
void evaluarLlegada() {
  verificando = false;
  switch (modo) {
    case Modo::IR:
      terminar(ResultadoDisco::OK);
      return;

    case Modo::VACIO:
      if (!vioAlgo) {
        terminar(ResultadoDisco::OK);
      } else if (empujones < 3) {
        empujones++;  // el lugar no estaba justo vacio: correrse medio slot y volver a mirar
        irHacia(pos + 0.5f);
      } else {
        terminar(ResultadoDisco::SLOT_OCUPADO);
      }
      return;

    case Modo::BUSCAR:
      if (vioObjetivo) {
        terminar(ResultadoDisco::OK);
        return;
      }
      faseBusqueda++;
      if (faseBusqueda == 1) {
        irHacia(slotEsperado + 1);
      } else if (faseBusqueda == 2) {
        irHacia(slotEsperado - 1);
      } else if (faseBusqueda == 3) {
        darVuelta();
      } else {
        terminar(ResultadoDisco::UID_NO_ENCONTRADO);
      }
      return;
  }
}

// --- Eventos del lector ---

void alEntrar(TagVisto &t) {
  if (tarea != Tarea::MOVER || dirSlots == 0) return;

  if (t.uid == UID_HOME) {
    // El centro del HOME esta medio tag mas adelante: ahi es el slot 0
    pos = normalizar(SLOT_HOME - dirSlots * anchoTag / 2);
    if (!vueltaCompleta) {
      restante = distanciaEnSentido(pos, objetivo, dirSlots);
      if (restante > SLOTS - 1) restante = 0;  // ya lo habiamos pasado: frenar aca
    }
  }
  if (modo == Modo::BUSCAR && t.uid == uidBuscado) {
    // Apareció la llave pedida: seguir medio tag para dejarla centrada en la ventana.
    // No se corrige la posicion con su slot: podria estar colgada en otro lugar.
    objetivo = normalizar(pos + dirSlots * anchoTag / 2);
    restante = anchoTag / 2;
    vueltaCompleta = false;
  }
}

void alSalir(TagVisto &t) {
  unsigned long ahora = millis();
  if (tarea == Tarea::HOMING && t.uid == UID_HOME) {
    ultimoHomeMs = ahora;
    if (homeAlEmpezar) {  // este paso empezo antes de que lo miraramos: no sirve
      homeAlEmpezar = false;
      return;
    }
    float centroMs = (t.primera + t.ultima) / 2.0f;
    if (faseHoming == 0) {
      centro1Ms = centroMs;
      anchoTag = (t.ultima - t.primera) / msPorSlot;
      faseHoming = 1;
      Serial.printf("[disco] HOME (1ra pasada). Ahora mido la vuelta...\n");
      return;
    }
    if (centroMs - centro1Ms < VUELTA_MS_INICIAL * 0.5f) return;  // rebote: el mismo paso
    msPorSlot = (centroMs - centro1Ms) / SLOTS;
    anchoTag = (t.ultima - t.primera) / msPorSlot;
    // Sentido de los slots mientras gira "adelante"
    int sentido = ADELANTE_SUMA_SLOTS ? 1 : -1;
    pos = normalizar(SLOT_HOME + sentido * (ahora - centroMs) / msPorSlot);
    tAnterior = ahora;
    listo = true;
    Serial.printf("[disco] Vuelta: %.1f s (%.0f ms por slot). Un tag dura %.2f slots en el lector.\n",
                  msPorSlot * SLOTS / 1000, msPorSlot, anchoTag);
    terminar(ResultadoDisco::OK);
    return;
  }

  if (tarea == Tarea::DIAGNOSTICO && cantMarcas < MAX_MARCAS) {
    float posUltima = normalizar(pos - dirSlots * (ahora - t.ultima) / msPorSlot);
    marcas[cantMarcas++] = {t.uid, t.posPrimera, posUltima};
  }
}

void leerLector() {
  String leidos[3];
  int n = rfidLeerTodos(leidos, 3);
  unsigned long ahora = millis();

  for (int i = 0; i < n; i++) {
    ultimoTag = leidos[i];
    TagVisto *t = nullptr;
    for (auto &v : vistos) {
      if (v.activo && v.uid == leidos[i]) t = &v;
    }
    if (t) {
      t->ultima = ahora;
      continue;
    }
    for (auto &v : vistos) {  // uno nuevo: ocupa un lugar libre
      if (!v.activo) {
        v.uid = leidos[i];
        v.primera = v.ultima = ahora;
        v.posPrimera = pos;
        v.activo = true;
        alEntrar(v);
        break;
      }
    }
  }
  for (auto &v : vistos) {
    if (v.activo && ahora - v.ultima > TAG_AUSENTE_MS) {
      v.activo = false;
      alSalir(v);
    }
  }
}

// --- Cada tarea, en cada vuelta del loop ---

void actualizarHoming() {
  unsigned long ahora = millis();
  unsigned long desde = ultimoHomeMs ? ultimoHomeMs : inicioHoming;
  if (ahora - desde > HOMING_TIMEOUT_MS) {
    Serial.println("[disco] No aparece el HOME: el motor no gira o el tag no esta");
    terminar(ResultadoDisco::HOME_NO_ENCONTRADO);
  }
}

void actualizarMover(float avance) {
  unsigned long ahora = millis();
  if (verificando) {
    for (auto &v : vistos) {
      if (!v.activo) continue;
      vioAlgo = true;
      if (v.uid == uidBuscado) vioObjetivo = true;
    }
    if (ahora - inicioVerificar >= VERIFICAR_MS) evaluarLlegada();
    return;
  }
  if (llegando) {  // esperando que el disco se quede quieto
    if (ahora - tLlegada >= FRENO_MS) {
      llegando = false;
      verificando = true;
      inicioVerificar = ahora;
      vioObjetivo = vioAlgo = false;
    }
    return;
  }
  restante -= avance;
  if (restante <= ADELANTO_FRENO_SLOTS) {
    if (vueltaCompleta) {  // dio la vuelta entera sin ver la llave
      terminar(ResultadoDisco::UID_NO_ENCONTRADO);
      return;
    }
    frenar();
    llegando = true;
    tLlegada = ahora;
  }
}

void actualizarDiagnostico(float avance) {
  recorrido += avance;
  if (recorrido < SLOTS + anchoTag) return;
  frenar();
  Serial.println("[disco] Diagnostico: que tag hay en cada slot");
  for (int i = 0; i < cantMarcas; i++) {
    float centro = normalizar(marcas[i].desde + distanciaCorta(marcas[i].desde, marcas[i].hasta) / 2);
    Serial.printf("  slot %2d (%5.2f): %s%s\n", (int)lroundf(centro) % SLOTS, centro, marcas[i].uid.c_str(),
                  marcas[i].uid == UID_HOME ? "  <- HOME" : "");
  }
  if (cantMarcas == 0) Serial.println("  No se leyo ningun tag");
  tarea = Tarea::NADA;
  resultado = ResultadoDisco::OK;
}

}  // namespace

void discoIniciar() {
  for (auto &v : vistos) v.activo = false;
}

void discoActualizar() {
  motorActualizar();
  float avance = integrar();
  leerLector();
  switch (tarea) {
    case Tarea::NADA: break;
    case Tarea::HOMING: actualizarHoming(); break;
    case Tarea::MOVER: actualizarMover(avance); break;
    case Tarea::DIAGNOSTICO: actualizarDiagnostico(avance); break;
  }
}

void discoHoming() {
  tarea = Tarea::HOMING;
  resultado = ResultadoDisco::EN_CURSO;
  faseHoming = 0;
  homeAlEmpezar = discoTagPresente(UID_HOME);
  inicioHoming = millis();
  ultimoHomeMs = 0;
  listo = false;
  girar(ADELANTE_SUMA_SLOTS ? 1 : -1);  // siempre gira "adelante"
}

void discoIrA(int slot) {
  uidBuscado = "";
  empezarMover(Modo::IR, slot);
}

void discoBuscar(const String &uid, int slot) {
  uidBuscado = uid;
  slotEsperado = slot;
  empezarMover(Modo::BUSCAR, slot);
  if (discoTagPresente(uid)) {  // ya esta en la ventana
    llegando = false;
    frenar();
    verificando = true;
    inicioVerificar = millis();
    vioObjetivo = vioAlgo = false;
  }
}

void discoIrAVacio(int slot) {
  uidBuscado = "";
  empezarMover(Modo::VACIO, slot);
}

void discoDiagnostico() {
  tarea = Tarea::DIAGNOSTICO;
  resultado = ResultadoDisco::EN_CURSO;
  cantMarcas = 0;
  recorrido = 0;
  girar(1);
}

void discoParar() {
  if (tarea != Tarea::NADA) terminar(ResultadoDisco::OK);
}

ResultadoDisco discoResultado() { return resultado; }

const char *discoTextoResultado(ResultadoDisco r) {
  switch (r) {
    case ResultadoDisco::EN_CURSO: return "en curso";
    case ResultadoDisco::OK: return "OK";
    case ResultadoDisco::HOME_NO_ENCONTRADO: return "no aparece el HOME";
    case ResultadoDisco::UID_NO_ENCONTRADO: return "la llave no esta en el disco";
    case ResultadoDisco::SLOT_OCUPADO: return "el lugar no esta vacio";
  }
  return "?";
}

bool discoListo() { return listo; }
int discoSlot() { return (int)lroundf(pos) % SLOTS; }
float discoPosicion() { return pos; }
float discoMsPorSlot() { return msPorSlot; }

bool discoTagPresente(const String &uid) {
  for (auto &v : vistos) {
    if (v.activo && v.uid == uid) return true;
  }
  return false;
}

bool discoHayTag() {
  for (auto &v : vistos) {
    if (v.activo) return true;
  }
  return false;
}

String discoTagEnVentana() {
  return discoTagPresente(ultimoTag) ? ultimoTag : "";
}
