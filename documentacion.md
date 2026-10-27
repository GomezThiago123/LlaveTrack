# LlaveTrack: documentación

Qué es el sistema, cómo funciona, cómo se conectan sus partes y en qué estado está cada historia.
Para levantarlo en la compu está el [README](README.md); la lista de tareas abiertas está en [PENDIENTES.md](PENDIENTES.md).

*Última actualización: 27/10/2026.*

---

## 1. Qué es

Un equipo que entrega y recibe las llaves de las aulas de la ETEC-UBA sin que nadie tenga que alcanzarlas.

Las llaves cuelgan de un disco de MDF con 32 lugares (*slots*). Cada llavero tiene un tag RFID. El docente pide la llave desde el celular, va al equipo, escribe un código y el disco gira hasta dejar su llave en la ventana. El sistema registra quién la retiró y a qué hora. Para devolverla, la cuelga en el lugar vacío de la ventana: el lector reconoce el tag y cierra el préstamo solo.

## 2. Cómo se usa

**Retirar una llave**
1. En la web, el docente toca **Pedir llave** en un aula disponible.
2. La web le muestra un **código de 6 dígitos** que vence en **2 minutos**.
3. En el equipo toca **A**, escribe el código y confirma con **#** (\* borra).
4. El disco gira, el lector comprueba que la llave de la ventana es la correcta y el LCD muestra "Aula 214 servida / RETIRE SU LLAVE".
5. Cuando el docente la saca, el LCD dice "Gracias" y el aula pasa a **Ocupada** en la web.

**Devolver una llave**
1. En el equipo toca **B**. El LCD dice "Cuelgue la llave".
2. La cuelga en el lugar vacío de la ventana. El lector la reconoce y el LCD muestra "Llave de aula 214 recibida". No hace falta apretar nada más.
3. El disco gira hasta dejar otro lugar vacío en la ventana, listo para la próxima devolución.

**Si algo falla**: si el equipo no encuentra la llave pedida después de dos intentos, el LCD dice "Pedi la llave en porteria" y el preceptor lo ve en la web, en **Problemas del equipo hoy**.

## 3. Las partes y cómo se conectan

```
  Celular / compu                        Nube (en la demo) o la compu (en desarrollo)
 ┌──────────────┐   HTTPS (JSON)   ┌──────────────────────┐        ┌───────────────┐
 │  Web (React) │ ───────────────► │  Servidor (Python,   │ ◄────► │ Base de datos │
 └──────────────┘                  │  FastAPI)            │        │ (Supabase)    │
                                   └──────────┬───────────┘        └───────────────┘
                                              │ MQTT
                                     ┌────────▼────────┐
                                     │ Broker MQTT     │
                                     │ (Mosquitto)     │
                                     └────────▲────────┘
                                              │ MQTT por WiFi
                                ┌─────────────┴──────────────┐
                                │ Equipo: ESP32 + lector RFID │
                                │ + LCD + teclado + motor     │
                                └────────────────────────────┘
```

- **La web nunca habla con el equipo.** Las dos hablan solo con el **servidor**, que es el único que decide (si el código vale, qué llave entregar) y el único que escribe en la base. Las horas de retiro y devolución las pone el servidor.
- **El equipo no tiene reglas propias.** Pide permiso, mueve el disco, lee tags y avisa lo que pasó.
- **MQTT** es un sistema de mensajes: el equipo y el servidor no se conectan entre sí, los dos se conectan al **broker** (Mosquitto), que reparte los mensajes. El contrato de cada mensaje está en [docs/protocolo-mqtt.md](docs/protocolo-mqtt.md).
- **El simulador** (`backend/simulador/`) se hace pasar por el equipo: manda exactamente los mismos mensajes. Por eso todo se puede probar sin el hardware, y el día que el ESP32 esté listo lo reemplaza sin cambiar nada del servidor ni de la web.

### Cómo se conecta el equipo real (cuando esté el firmware)
1. **El firmware** (Fase 3) se configura en `firmware/include/secrets.h` con la red WiFi, la dirección del broker y el usuario del equipo.
2. **El equipo se conecta al WiFi y al broker**, y anuncia que está en línea. En la web aparece "Equipo en línea" y se habilita "Pedir llave". Si se corta, a los ~15 segundos la web lo muestra desconectado.
3. **Mosquitto tiene que aceptar conexiones de la red.** Como está instalado hoy (sin configuración propia, Mosquitto 2) solo acepta conexiones de la misma compu: el simulador entra, el ESP32 no. Para probar el equipo en la compu hay que agregar a `mosquitto.conf` un `listener 1883` y `allow_anonymous true`, y abrir el puerto en el firewall. En la demo, el broker va en la nube con contraseña por equipo y cifrado (puerto 8883).
4. **El WiFi**: la red de la escuela es WPA2-Enterprise (usuario y contraseña por persona). El equipo se puede conectar, pero hace falta una cuenta para él y que la red deje salir al puerto 8883. Plan B: el hotspot de un celular.

### Cómo se conecta el celular
- **En desarrollo**: el celular en el mismo WiFi que la compu entra a `http://<IP-de-la-compu>:5173`.
- **En la demo**: el servidor y la web van a un hosting en la nube con dominio y HTTPS. Conviene que esté en la misma región que Supabase (Virginia, EE. UU.): desde Argentina cada consulta a la base tarda ~170 ms, y en la misma región, 1 o 2 ms.

## 4. Cómo sabe el sistema qué llave es cada una

Cada llavero tiene un **tag RFID con un número único de fábrica (UID)**, por ejemplo `04A1B2C3`. El lector no "sabe" de aulas: solo lee ese número. La relación **UID ↔ aula ↔ lugar del disco** está guardada en la base (tabla `llave`).

- **Al retirar**, el servidor le dice al equipo "andá al slot 19 y verificá que esté el UID `04A00214`". El equipo gira y compara lo que lee contra ese número exacto. El lector puede ver tags vecinos, por eso nunca acepta "cualquier tag".
- **Al devolver**, el equipo lee el UID de la llave que colgaron y el servidor busca de qué aula es y quién la tenía.
- **El slot 0** tiene un tag especial, **HOME**, que nunca se presta: le sirve al equipo para saber dónde está el cero del disco al arrancar.

### Las llaves cargadas hoy
Por pedido del profe se arranca con **5 llaves**, con sus UID reales (leídos con NFC Tools el 27/10/2026; son tags MIFARE Classic 1K):

| Aula | UID | Slot |
| --- | --- | --- |
| 101 | `A94B37A4` | 1 |
| 102 | `2A86C880` | 2 |
| 213 | `5A81F281` | 3 |
| 214 | `CAA8EA81` | 4 |
| 313 | `2AC3FE80` | 5 |

Falta leer el tag **HOME** (slot 0). Las 30 aulas, con UID inventados, quedan en `backend/seed/datos_30_aulas.json`.

### Cómo se cargan más llaves
1. **Marcar cada llavero** con el número de su aula (con fibra o una etiqueta).
2. **Leer el UID de cada tag.** Dos formas:
   - **Ya mismo, con un celular Android con NFC**: la app gratuita *NFC Tools* muestra el número de serie al acercar el tag (ej. `04:A1:B2:C3`). Funciona con la mayoría de los tags de 13,56 MHz. Ojo: algunas apps muestran los bytes en orden inverso, así que conviene comparar uno con lo que lee el equipo antes de cargar los 30.
   - **Con el equipo**, cuando esté el firmware: el modo diagnóstico (mantener **D** al encender) recorre el disco y lista qué UID hay en cada slot.
3. **Cargarlo en el sistema**:
   - **Desde la web**: preceptor → **Equipo** → Tags RFID → el lápiz del aula. Acepta el número con o sin dos puntos y avisa si ese tag ya es de otra aula.
   - **O en `backend/seed/datos.json`** y recargar la base (`python -m app.seed --reiniciar`, que borra los datos de prueba).
4. **Colgar cada llave en su slot**: el slot de cada aula se ve en la misma pantalla de Equipo (hoy: 101 en el 1, 102 en el 2, 213 en el 3, 214 en el 4 y 313 en el 5). Si una llave queda en otro lugar, al retirarla el equipo la busca dando una vuelta (es más lento), y al devolverla el sistema guarda el slot donde la leyó. Conviene colgarlas bien desde el principio.

## 5. La web

| Quién | Pantallas (barra de abajo) |
| --- | --- |
| Sin login | Estado de las 30 aulas y del equipo, login, recuperar contraseña |
| Docente | **Aulas** (buscador, pisos, "solo disponibles", pedir llave y el código arriba) · **Mis llaves** (las que tengo y mis préstamos) · **Cuenta** |
| Preceptor y admin | **Aulas** · **Faltantes** (quién tiene cada llave, desde cuándo, "Enviar recordatorio") · **Historial** (filtros por aula, docente, fechas y estado) · **Equipo** (estado, carrusel, problemas, tags RFID) · **Docentes** (cuentas bloqueadas, alta, activar o desactivar) |

Diseño: el [prototipo de Joel](https://github.com/joel012930/llavetrack), con los colores de la UBA. Las pantallas se actualizan solas cada 5 segundos. La sesión se cierra tras 60 segundos sin actividad, salvo mientras se muestra el código.

## 6. Estado de las historias

Las historias completas, con sus criterios, están en [docs/user-stories.md](docs/user-stories.md). "Servidor y simulador" significa que funciona de punta a punta con el simulador y falta el firmware del equipo real (Fase 3).

| US | Historia | Release | Estado |
| --- | --- | --- | --- |
| US-01 | Iniciar sesión | MVP | ✅ Hecha (Google, más adelante) |
| US-02 | Consultar aulas disponibles | MVP | ✅ Hecha |
| US-03 | Solicitar la llave | MVP | ✅ Hecha |
| US-04 | Retirar la llave | MVP | 🟡 Servidor y simulador |
| US-05 | Recibir siempre la llave correcta | MVP | 🟡 Servidor y simulador |
| US-06 | Devolver la llave | MVP | 🟡 Servidor y simulador |
| US-07 | Bloqueo por intentos fallidos | MVP | ✅ Hecha |
| US-08 | Recuperar contraseña | MVP | ✅ Hecha (falta configurar el mail de verdad) |
| US-09 | Registrar docentes | V2 | ✅ Hecha |
| US-10 | Dar de alta una llave | V2 | 🟡 El UID se carga a mano (falta el "modo alta" del equipo) |
| US-11 | Dar de baja una llave perdida | V2 | ⬜ Falta |
| US-12/13 | Historial por aula y por docente | V2 | ✅ Hecha |
| US-14 | Devolver sin conexión | V2 | ⬜ Falta |
| US-15 | Corte de luz durante un retiro | V2 | ⬜ Falta |
| US-16 | Recordatorio de devolución | V2 | 🟡 Lo manda el preceptor (el sistema no conoce los turnos) |
| US-17 | Ver mis llaves | V2 | ✅ Hecha |
| US-18 | Retiro con credencial | V2 | ⬜ Falta |
| US-19 | Exportar reportes | V2 | ⬜ Falta |
| US-20 | Devolver una llave retirada por otro | V2 | ⬜ Falta (hoy cualquiera la devuelve y queda a nombre de quien la retiró) |
| US-21 | Registrar incidentes del equipo | V2 | 🟡 Se registran y se ven; falta marcarlos resueltos |
| US-22 | Ver si el equipo está conectado | MVP | ✅ Hecha |
| US-23 | Ver en el equipo qué llaves faltan | MVP | 🟡 Servidor y simulador |
| US-24 | Ver en el equipo si está conectado | MVP | 🟡 Servidor y simulador |

## 7. Decisiones importantes

| Fecha | Decisión | Por qué |
| --- | --- | --- |
| 20/10 | El código dura **2 minutos** y la sesión se cierra a los **60 s** sin actividad | Lo piden US-03 y US-01. La pantalla del código no deja que se cierre la sesión mientras el docente va al equipo |
| 20/10 | **Todos los usuarios** ven quién tiene cada llave y su teléfono | US-02 |
| 20/10 | La **devolución se confirma sola** al leer el tag | Es más simple, y evita llaves colgadas que figuren como prestadas porque nadie apretó "confirmar" |
| 20/10 | La base es **Supabase** (PostgreSQL), solo como base | La web y el equipo pasan siempre por el servidor. Las tablas tienen RLS para que la API pública de Supabase no exponga nada |
| 20/10 | El disco tiene **32 slots**: el 0 es el tag HOME y entran las 30 aulas | Fotos y medidas del equipo |
| 20/10 | El motor es un **motorreductor de continua de 24 V**, no un paso a paso | Etiqueta del motor. Sin pasos que contar, la posición va a salir de un sensor que cuente las pestañas del disco (pendiente) |
| 20/10 | Las historias del equipo conectado y los LEDs son **US-22 a US-24** | En Notion, US-20 y US-21 eran otras. Los commits viejos dicen US-20 a US-22 |
| 20/10 | El equipo usa la **WiFi de la escuela** (plan B: hotspot) | Respuesta del grupo |
| 21/10 | La web toma el **diseño del prototipo de Joel** con los colores de la UBA | Con 30 aulas, la grilla con buscador y pisos es mucho más cómoda que la lista |

## 8. Cómo se prueba

- **Tests automáticos del servidor**: `pytest` en `backend/` (129 tests). Incluyen dos pedidos simultáneos por la misma llave, el vencimiento de reservas, los eventos repetidos del equipo y que ninguna lista haga una consulta por cada fila.
- **Simulador**: reemplaza al equipo. Comandos `retirar`, `devolver`, `falla`, `timeout`, `desenchufar` y `enchufar` (ver README).
- **La web**: se revisó pantalla por pantalla con capturas automáticas en tamaño de celular, con datos de prueba y contra Supabase.

## 9. Dónde está cada cosa

| Archivo | Qué tiene |
| --- | --- |
| [README.md](README.md) | Cómo instalar y levantar el servidor, la web y el simulador |
| [PENDIENTES.md](PENDIENTES.md) | Tareas abiertas y preguntas que faltan responder |
| [docs/user-stories.md](docs/user-stories.md) | Las historias de Notion con sus criterios de aceptación |
| [docs/protocolo-mqtt.md](docs/protocolo-mqtt.md) | Los mensajes entre el equipo y el servidor |
| [CLAUDE.md](CLAUDE.md) | La especificación técnica completa (reglas, API, firmware, hardware) |
