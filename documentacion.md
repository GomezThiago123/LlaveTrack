# LlavesUBA: documentación

Qué es el sistema, cómo funciona, cómo se conectan sus partes y en qué estado está cada historia.
Para levantarlo en la compu está el [README](README.md); la lista de tareas abiertas está en [PENDIENTES.md](PENDIENTES.md).

*Última actualización: 03/11/2026.*

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

### Cómo se conecta el equipo real
1. **El firmware** (Fase 3, en `firmware/`) se configura en `firmware/include/secrets.h` con la red WiFi, la dirección del broker y el usuario del equipo. Están hechos y probados en el equipo el paso 1 (el disco sin red: homing con el tag HOME, búsqueda de llaves y lugar vacío), que ahora es el **modo diagnóstico** (tecla D apretada al encender), el **paso 2a** (la red): WiFi común o WPA2-Enterprise, MQTT con reconexión, aviso de "en línea" con latido, `inicio`, la hora y las llaves faltantes en el LCD, y el LED; y el **paso 2b** (el retiro y la devolución).
2. **El equipo se conecta al WiFi y al broker**, y anuncia que está en línea. En la web aparece "Equipo en línea" y se habilita "Pedir llave". Si se corta, a los ~15 segundos la web lo muestra desconectado. Probado el 03/11/2026: se conecta, el servidor le dice qué lugar vacío dejar en la ventana, y si el servidor se cae el LCD dice "Sin conexion / Servidor" en el mismo segundo; cuando vuelve, se recupera solo.
3. **Mosquitto tiene que aceptar conexiones de la red.** Instalado sin configuración propia (Mosquitto 2) solo acepta conexiones de la misma compu: el simulador entra, el ESP32 no. En la notebook se agregó `/etc/mosquitto/conf.d/llavetrack.conf` (`listener 1883 0.0.0.0` y `allow_anonymous true`) y el firewall abre el 1883 **solo para la IP del ESP32**, porque el broker no tiene contraseña. En la demo, el broker es HiveMQ Cloud, con contraseña por equipo y cifrado (puerto 8883): el equipo sale hacia internet y ya no hace falta abrir nada en una compu.
4. **El WiFi**: se decidió usar la red de la escuela, que es WPA2-Enterprise (usuario y contraseña por persona): hace falta una cuenta para el equipo y que la red deje salir al puerto 8883. En las pruebas se usó **PEINE-3**, una WiFi común de la escuela (con contraseña, en 2,4 GHz): el ESP32 se conecta y llega a la notebook. Plan B: el hotspot de un celular.

### Cómo se conecta el celular
- **En desarrollo**: el celular en el mismo WiFi que la compu entra a `http://<IP-de-la-compu>:5173`.
- **En la demo**: el servidor y la web van en Render, en una dirección `*.onrender.com` con HTTPS. Está en la misma región que Supabase (Virginia, EE. UU.): desde Argentina cada consulta a la base tarda ~170 ms, y en la misma región debería tardar milisegundos. Cómo subirlo: [docs/despliegue.md](docs/despliegue.md).

## 4. Cómo sabe el sistema qué llave es cada una

Cada llavero tiene un **tag RFID con un número único de fábrica (UID)**, por ejemplo `04A1B2C3`. El lector no "sabe" de aulas: solo lee ese número. La relación **UID ↔ aula ↔ lugar del disco** está guardada en la base (tabla `llave`).

- **Al retirar**, el servidor le dice al equipo "andá al slot 19 y verificá que esté el UID `04A00214`". El equipo gira y compara lo que lee contra ese número exacto. El lector puede ver tags vecinos, por eso nunca acepta "cualquier tag".
- **Al devolver**, el equipo lee el UID de la llave que colgaron y el servidor busca de qué aula es y quién la tenía.
- **El slot 0** tiene un tag especial, **HOME**, que nunca se presta: le sirve al equipo para saber dónde está el cero del disco al arrancar.

### Las llaves cargadas hoy
El sistema trabaja con **6 llaves**: las 5 que pidió el profe el 27/10/2026 más la de la **104**, que se sumó el 03/11/2026. Son tags MIFARE Classic 1K, y los UID se relevaron con el lector del equipo el 03/11/2026. Los slots siguen el orden en que quedaron colgadas, a partir del HOME:

| Aula | UID | Slot |
| --- | --- | --- |
| 101 | `9AAFF281` | 1 |
| 102 | `2A86C880` | 2 |
| 104 | `9A35EA81` | 3 |
| 213 | `5A81F281` | 4 |
| 214 | `CAA8EA81` | 5 |
| 313 | `2AC3FE80` | 6 |

El tag **HOME** (slot 0, nunca sale del disco) es `A94B37A4`. No va en la base: lo usa el equipo para encontrar el cero al arrancar, y se carga en `config.h` del firmware. La lista del 27/10, armada a mano con NFC Tools, tenía cruzados el HOME y la 101; el diagnóstico del equipo lo detectó.

### Cómo se carga o se cambia una llave (por ejemplo, si se pierde un llavero)
1. **Marcar cada llavero** con el número de su aula (con fibra o una etiqueta).
2. **Leer el UID de cada tag.** Dos formas:
   - **Ya mismo, con un celular Android con NFC**: la app gratuita *NFC Tools* muestra el número de serie al acercar el tag (ej. `04:A1:B2:C3`). Funciona con la mayoría de los tags de 13,56 MHz. Ojo: algunas apps muestran los bytes en orden inverso, así que conviene comparar uno con lo que lee el equipo antes de cargar los demás.
   - **Con el equipo** (lo más seguro): el modo diagnóstico (mantener **D** al encender) da una vuelta al disco y lista qué UID hay en cada slot. Así se armó la lista de arriba.
3. **Cargarlo en el sistema**:
   - **Desde la web**: preceptor → **Equipo** → Tags RFID → el lápiz del aula. Acepta el número con o sin dos puntos y avisa si ese tag ya es de otra aula.
   - **O en `backend/seed/datos.json`** y recargar la base (`python -m app.seed --reiniciar`, que borra los datos de prueba).
4. **Colgar cada llave en su slot**: el slot de cada aula se ve en la misma pantalla de Equipo (hoy, los de la tabla de arriba). Si una llave queda en otro lugar, al retirarla el equipo la busca dando una vuelta (es más lento), y al devolverla el sistema guarda el slot donde la leyó. Conviene colgarlas bien desde el principio.

## 5. La web

| Quién | Pantallas (barra de abajo) |
| --- | --- |
| Sin login | Estado de las aulas y del equipo, login, recuperar contraseña |
| Docente | **Aulas** (buscador, peines 1, 2 y 3, "solo disponibles", pedir llave y el código arriba) · **Mis llaves** (las que tengo y mis préstamos) · **Cuenta** |
| Preceptor y admin | **Aulas** · **Faltantes** (quién tiene cada llave, desde cuándo, "Enviar recordatorio") · **Historial** (filtros por aula, docente, fechas y estado) · **Equipo** (estado, carrusel, problemas, tags RFID, "Recalibrar el disco") · **Docentes** (cuentas bloqueadas, alta, activar o desactivar) |

Diseño: el [prototipo de Joel](https://github.com/joel012930/llavetrack), con los colores de la UBA. Las pantallas se actualizan solas cada 5 segundos. La sesión se cierra tras 60 segundos sin actividad, salvo mientras el docente tiene una reserva pendiente (aunque bloquee el celular camino al equipo).

## 6. Estado de las historias

Las historias completas, con sus criterios, están en [docs/user-stories.md](docs/user-stories.md). "Servidor y simulador" significa que funciona de punta a punta con el simulador y falta el firmware del equipo real (Fase 3).

| US | Historia | Release | Estado |
| --- | --- | --- | --- |
| US-01 | Iniciar sesión | MVP | ✅ Hecha |
| US-02 | Consultar aulas disponibles | MVP | ✅ Hecha |
| US-03 | Solicitar la llave | MVP | ✅ Hecha. Desde el 05/11, sin código: al apretar "Pedir llave" el equipo la entrega enseguida (probado con el equipo real) |
| US-04 | Retirar la llave | MVP | ✅ Probada con el equipo real (03 y 04/11), también el tiempo agotado y la tecla C |
| US-05 | Recibir siempre la llave correcta | MVP | ✅ Probada con el equipo real (04/11): sin la llave en el disco, dos intentos, "Pedi la llave en porteria" y el incidente para el preceptor |
| US-06 | Devolver la llave | MVP | ✅ Probada con el equipo real (03 y 04/11), también "Llave no reconocida" |
| US-07 | Bloqueo por intentos fallidos | MVP | ✅ Hecha |
| US-08 | Recuperar contraseña | MVP | ✅ Hecha (falta configurar el mail de verdad) |
| US-09 | Registrar docentes | V2 | ✅ Hecha |
| US-10 | Dar de alta una llave | V2 | 🟡 Hecha (04/11): "modo alta" desde la pantalla Equipo; el equipo lee el tag y se asocia a un aula. Falta probarla con el equipo real |
| US-11 | Dar de baja una llave perdida | V2 | ✅ Hecha (04/11): con motivo; deja de aparecer para retiro, el historial muestra la baja y el último docente, y se repone con un tag nuevo |
| US-12/13 | Historial por aula y por docente | V2 | ✅ Hecha |
| US-14 | Devolver sin conexión | V2 | 🟡 Hecha (04/11): el equipo guarda la devolución con su hora y la manda al volver la conexión. Falta probarla con el equipo real |
| US-15 | Corte de luz durante un retiro | V2 | 🟡 Hecha (04/11): al volver la luz el equipo avisa, se cancela la reserva y el LCD dice "Equipo listo". Falta probarla con el equipo real |
| US-16 | Recordatorio de devolución | V2 | ✅ Hecha (04/11): al pedir la llave el docente dice hasta qué hora usa el aula; 15 min después le llega un mail y a la hora el preceptor la ve "Demorada". El preceptor también puede mandarlo a mano |
| US-17 | Ver mis llaves | V2 | ✅ Hecha |
| US-18 | Retiro con credencial | V2 | ✅ Hecha y probada con el equipo real (05/11): para el que olvidó el celular, DNI y número de aula en el teclado ("Hola Bruno / Aula 214") |
| US-19 | Exportar reportes | V2 | ✅ Hecha (04/11): botón "Exportar a Excel" en el historial, con los mismos filtros; deshabilitado si no hay movimientos |
| US-20 | Devolver una llave retirada por otro | V2 | 🟡 Hecha (04/11): quien devuelve puede escribir su DNI; si la llave era de otro, confirma con # y al titular le llega un mail. Falta probarla con el equipo real |
| US-21 | Registrar incidentes del equipo | V2 | ✅ Hecha (04/11): mientras un incidente está abierto, el aula figura "En revisión" y no se puede reservar; el preceptor lo marca resuelto |
| US-22 | Ver si el equipo está conectado | MVP | ✅ Hecha |
| US-23 | Ver en el equipo qué llaves faltan | MVP | 🟡 El LCD muestra "Faltan: 214" con el equipo real; el LED naranja no se vio (revisar el LED) |
| US-24 | Ver en el equipo si está conectado | MVP | 🟡 Probada con el equipo real (LCD y LED verde); falta ver el LED rojo titilando |

## 7. Decisiones importantes

| Fecha | Decisión | Por qué |
| --- | --- | --- |
| 05/11 | El sistema se llama **LlavesUBA** (antes LlaveTrack) | Pedido de los superiores |
| 05/11 | **Entrega directa:** al apretar "Pedir llave" en la web, el equipo entrega la llave enseguida; ya no hay código que escribir | Pedido de los superiores: más simple. Hay que pedirla frente al equipo, porque queda un minuto en la ventana |
| 05/11 | El teclado es solo para el que olvidó el celular: **DNI y número de aula** | Pedido de los superiores. El DNI no es secreto: queda registrado a nombre de ese docente y 3 intentos mal bloquean el teclado |
| 05/11 | Al iniciar sesión se arranca en **Aulas** | Pedido de los superiores |
| 20/10 | El código dura **2 minutos** y la sesión se cierra a los **60 s** sin actividad | Lo piden US-03 y US-01. La pantalla del código no deja que se cierre la sesión mientras el docente va al equipo |
| 20/10 | **Todos los usuarios** ven quién tiene cada llave y su teléfono | US-02 |
| 20/10 | La **devolución se confirma sola** al leer el tag | Es más simple, y evita llaves colgadas que figuren como prestadas porque nadie apretó "confirmar" |
| 20/10 | La base es **Supabase** (PostgreSQL), solo como base | La web y el equipo pasan siempre por el servidor. Las tablas tienen RLS para que la API pública de Supabase no exponga nada |
| 20/10 | El disco tiene **32 slots**: el 0 es el tag HOME y entran las 30 aulas | Fotos y medidas del equipo |
| 20/10 | El motor es un **motorreductor de continua de 24 V**, no un paso a paso | Etiqueta del motor. Sin pasos que contar, la posición va a salir de un sensor que cuente las pestañas del disco (pendiente) |
| 20/10 | Las historias del equipo conectado y los LEDs son **US-22 a US-24** | En Notion, US-20 y US-21 eran otras. Los commits viejos dicen US-20 a US-22 |
| 20/10 | El equipo usa la **WiFi de la escuela** (plan B: hotspot) | Respuesta del grupo |
| 27/10 | El firmware usa **el cableado que hicieron los compañeros** (`docs/cableado.md`): un LED bicolor y el motor sin control de velocidad | Ya estaba armado: es más fácil adaptar el código que volver a cablear |
| 27/10 | LED bicolor: **verde** = todo bien, **naranja** = falta alguna llave, **rojo titilando** = sin conexión | Hay un solo LED cableado para mostrar las dos cosas |
| 27/10 | La posición del disco sale del **lector RFID y el tiempo de giro**, sin sensor extra | El retiro frena al leer la llave pedida; el lugar vacío se calcula por tiempo desde el último tag conocido. Una vuelta tarda entre 24 y 47 s según el día (medido el 03 y el 04/11): el equipo la mide en cada arranque. Si no alcanza la precisión, se agrega un sensor de horquilla |
| 03/11 | Se suma la llave de la **104**: quedan **6 llaves** | Estaba en el disco con su tag |
| 04/11 | Las llaves quedan en orden desde el HOME: 101, 102, 104, 213, 214 y 313 (slots 1 a 6) | Se recolgaron. Ese día el motor giraba al revés y al doble de velocidad que el 03/11 sin que nadie dijera haber tocado la conexión: el firmware se ajustó (`ADELANTE_SUMA_SLOTS`) y mide la vuelta en cada arranque |
| 03/11 | El firmware **compensa la holgura** del disco al invertir el giro (~0,85 slot) y, al buscar una llave, **sigue un poco más** del lugar esperado | Medido en el equipo: el engranaje tiene juego y la velocidad del motor varía un poco entre vueltas |
| 03/11 | La nube es **gratis y sin dominio propio**: Render, HiveMQ Cloud, Brevo y Supabase, con un ping cada 10 min para que Render no se duerma | No hay presupuesto. Si fallan el día de la demo, el plan B es todo en una compu con un hotspot |
| 03/11 | El login es **solo con email y contraseña**, sin Google | US-01 no pide Google y debilita el login. Con una sola forma de entrar, el bloqueo por intentos (US-07) cubre todos los ingresos |
| 21/10 | La web toma el **diseño del prototipo de Joel** con los colores de la UBA | Con 30 aulas, la grilla con buscador y peines es mucho más cómoda que la lista |

## 8. Cómo se prueba

- **Tests automáticos del servidor**: `pytest` en `backend/` (139 tests). Incluyen dos pedidos simultáneos por la misma llave, el vencimiento de reservas, los eventos repetidos del equipo y que ninguna lista haga una consulta por cada fila.
- **Simulador**: reemplaza al equipo. Comandos `retirar`, `devolver`, `falla`, `timeout`, `desenchufar` y `enchufar` (ver README). También se conecta al broker de la nube, con cifrado y contraseña.
- **Ensayo de la nube** (03/11): la imagen que corre Render, en una compu, contra un broker con cifrado, contraseña y permisos por equipo. Falta repetirlo con los servicios reales y con la placa.
- **La web**: se revisó pantalla por pantalla con capturas automáticas en tamaño de celular, con datos de prueba y contra Supabase.
- **El disco del equipo** (03/11): con el modo diagnóstico, desde el Monitor Serie. Se probaron el homing (encuentra el HOME y mide la vuelta), el diagnóstico (lista los 7 tags en su slot), la búsqueda de una llave para los dos sentidos de giro (frena con la llave centrada en la ventana, sin control de velocidad) y el lugar vacío en la ventana. El lector lee los tags con el disco girando a velocidad plena.
- **El retiro y la devolución con el equipo real** (03/11): pedido desde la web, código en el teclado, el disco trae la llave, se registra el préstamo al sacarla y la devolución al colgarla. Un ciclo completo: ~55 s el retiro (la mayor parte es escribir el código) y ~10 s la devolución.

## 9. Dónde está cada cosa

| Archivo | Qué tiene |
| --- | --- |
| [README.md](README.md) | Cómo instalar y levantar el servidor, la web y el simulador |
| [PENDIENTES.md](PENDIENTES.md) | Tareas abiertas y preguntas que faltan responder |
| [docs/user-stories.md](docs/user-stories.md) | Las historias de Notion con sus criterios de aceptación |
| [docs/protocolo-mqtt.md](docs/protocolo-mqtt.md) | Los mensajes entre el equipo y el servidor |
| [docs/despliegue.md](docs/despliegue.md) | Cómo subir el sistema a la nube, gratis |
| [CLAUDE.md](CLAUDE.md) | La especificación técnica completa (reglas, API, firmware, hardware) |
