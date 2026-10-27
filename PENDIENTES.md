# Pendientes de LlaveTrack

Última actualización: 20/10/2026. Hechas hasta ahora: Fase 0, Fase 1, Fase 2 (salvo Google), US-22, US-23 y US-24 en el servidor y el simulador, la base en Supabase y el seed con las 30 aulas.

## 0. Lo último (hasta el 21/10/2026)

- [x] **Rediseño de la web** con el [prototipo de Joel](https://github.com/joel012930/llavetrack) y los colores de la UBA (azul, celeste y blanco): todas las pantallas, probadas con capturas en tamaño de celular (21/10/2026).
- [x] **V2 en el servidor** (en `main`): US-17 mis préstamos, US-12/13 historial, US-16 recordatorio (a mano: el sistema no conoce los turnos), US-09 alta y desactivar docentes, US-10 cambiar el tag RFID (a mano hasta el modo alta del equipo). Supabase ya tiene las migraciones.
- [x] **Vite actualizado a 8.3.3** (la 8.3.2 tenía una falla de seguridad). `npm audit`: 0 fallas.
- [x] **Las listas del servidor ya no hacen una consulta por fila** (con Supabase, `/api/aulas` tardaba 6,7 s y la web se quedaba en "Cargando…"; ahora 1,6 s). Hay un test que lo controla.
- [x] **`documentacion.md`** con qué es el sistema, cómo se conectan las partes, cómo se asocia cada llave con su tag, el estado de cada US y las decisiones. Se actualiza junto con este archivo.
- [x] **Probado en el entorno real** (servidor + Supabase + simulador + web, 21/10/2026): ciclo retiro → devolución, bloqueo y desbloqueo de Bruno (US-07) y todas las pantallas.

## 1. Respuestas que necesito de vos

Bloquean trabajo: sin estas respuestas no se puede seguir con lo que dice cada una.

- [x] **Decisiones sobre las user stories** (sección 2b): lo construido no coincide con algunos criterios de aceptación.
- [ ] **Sensor de posición:** el motor es un motorreductor de continua de 24 V y 2 cables (no es paso a paso), así que la posición sale de contar las 32 pestañas del disco. ¿Tienen un sensor para eso (ej. óptico de horquilla) o hay que conseguirlo? Con eso reescribo el diseño del motor en el CLAUDE.md. *Bloquea: la Fase 3 (motor).*
- [ ] **LEDs:** dos bicolores (conexión y faltantes). En la Fase 3 propongo los colores, GPIO y resistencias.
- [ ] **Proveedor de la nube** para el servidor (ver la sección 3). Lo propongo yo cuando lleguemos.
- [ ] **WiFi de la escuela (decidido: el ESP32 se conecta ahí):** es WPA2-Enterprise. Hace falta:
  - El nombre de la red y el método de acceso (casi siempre PEAP; lo sabe sistemas).
  - Una cuenta para el equipo: mejor una que dé sistemas para el proyecto, no la personal de alguien (queda guardada en el equipo).
  - Saber si pide un certificado.
  - Probar que la red deja salir al puerto 8883 (MQTT con TLS): desde una notebook en esa WiFi, en MQTTX conectarse a `test.mosquitto.org`, puerto 8883, con SSL. Si conecta, el puerto está abierto. Si no, plan B: hotspot de un celular.

### Ya respondidas (20/10/2026)

- **Disco:** 32 slots. El 0 es del tag HOME, así que quedan 31 lugares: entran las 30 aulas y sobra 1.
- **Aula 105:** el asterisco era un error; es un aula como las demás.
- **Placa:** NodeMCU ESP32 de 38 pines con USB-C (módulo ESP-WROOM-32).
- **LCD:** 16x2. La dirección I2C sale del scanner en la Fase 3.
- **Referencia de cero:** el tag RFID HOME en el slot 0, por ahora.
- **Servidor de la demo:** en la nube.
- **Seed con las 30 aulas:** OK.
- **User stories:** recibidas y guardadas en `docs/user-stories.md`.
- **WiFi:** la de la escuela (WPA2-Enterprise).
- **LEDs:** dos bicolores, uno por agujero del panel.

## 2. Lo próximo en el código

En el orden acordado. Cada uno arranca con un plan corto y espera tu OK.

- [x] **US-23: LED y LCD de llaves faltantes.** Hecho en el servidor y el simulador; en el equipo se hace en la Fase 3.
- [x] **US-24: LED de conexión con el servidor.** Hecho en el servidor y el simulador (el LED titila mientras no hay conexión); en el equipo se hace en la Fase 3.
- [x] **Seed con las 30 aulas reales** (101–105, 111–115, 201–205, 211–215, 301–305, 311–315): `slotsTotales: 32`, slot 0 para HOME, aulas en los slots 1 a 30 y UID inventados (`04A0` + aula, ej. `04A00214`) hasta el modo diagnóstico. El simulador usa `--slots 32` por defecto. Los tests usan sus propios datos (`tests/datos_prueba.json`) y un test valida el seed real.
- [x] **Documentación de US-22 a US-24:** tópicos nuevos (`latido`, `faltantes`, `servidor/estado`), `EQUIPO_TIMEOUT_SEGUNDOS` y reglas de los LEDs en el CLAUDE.md, `docs/protocolo-mqtt.md` y el README.
- [x] **Revisar lo construido contra los criterios de aceptación.** Las diferencias están en la sección 2b.

## 2b. Diferencias con las user stories (`docs/user-stories.md`)

Esperan tu decisión. Después armo un plan y espero tu OK.

- [x] **Numeración:** las historias del equipo conectado, las llaves faltantes y la conexión del equipo se cargaron en Notion como US-22, US-23 y US-24 (MVP) y se renombraron en el código y la documentación. Los commits viejos dicen US-20/21/22.
- [x] **US-01, sesión de 60 s** (implementado) (hoy 15 min). Decidido: 60 s, salvo mientras está abierta la pantalla del código. Falta implementarlo.
- [x] **US-02, quién ve quién tiene la llave** (implementado): decidido: todos los usuarios logueados ven nombre, hora y teléfono (hoy solo el preceptor y el admin). Falta implementarlo.
- [x] **US-03, la reserva vence a los 2 min** (implementado): decidido: 2 min por defecto (hoy 10). Falta implementarlo; acordate de borrar `RESERVA_MINUTOS=3` de tu `.env`.
- [x] **US-05, incidente visible para el preceptor:** tabla `Incidente`, `GET /api/incidentes` y el cuadro "Problemas del equipo hoy" del preceptor. En el simulador: `falla <codigo>`. En el equipo se hace en la Fase 3.
- [x] **US-06, "cuando confirmo":** decidido: automático, como ahora (alcanza con colgar la llave). El criterio ya se ajustó en Notion y en `docs/user-stories.md` (21/10/2026).
- [x] **US-07, desbloqueo manual por el preceptor:** cuadro "Cuentas bloqueadas" en la lista de aulas del preceptor y el admin.
- [x] **Textos exactos de los criterios** (los del firmware quedan en el CLAUDE.md para la Fase 3): "Usuario o contraseña incorrectos" (hoy "Email o…"), "Ocupada" (hoy "Prestada"), "Cuenta bloqueada temporalmente", "Si el email está registrado, te enviamos un link", y en el LCD "Aula X servida / RETIRE SU LLAVE", "Gracias X" al retirar, "Reposicionando / Espere...", "Pedi la llave / en porteria" y "Llave de aula X recibida" (todo de 16 caracteres por línea y sin tildes).

## 3. El servidor en la nube

Como la demo corre en la nube, hay cosas nuevas para resolver antes de la Fase 4:

- [ ] **Elegir proveedor:** tiene que poder correr el servidor de Python **y** Mosquitto, que necesita un puerto TCP propio. Los hostings que solo sirven páginas web no alcanzan.
  - **En la misma región que Supabase (us-east-1, Virginia).** Medido el 20/10/2026 con el servidor en Argentina: cada consulta a Supabase tarda ~170 ms, y un evento del equipo hace 10–12, así que la respuesta tarda 2–5 s y el equipo llega a mostrar "Sin respuesta" (espera 5 s). En la misma región baja a milisegundos.
  - Para desarrollar desde casa conviene SQLite local (comentar `DATABASE_URL` en el `.env`).
- [ ] **Dominio con HTTPS** para la web y la API.
- [ ] **Mosquitto expuesto a internet:** TLS en el puerto 8883, usuario y contraseña por equipo y una ACL por prefijo. Nunca el 1883 abierto. El ESP32 se conecta con `WiFiClientSecure` y el certificado raíz.
- [x] **Base persistente:** PostgreSQL de Supabase (`DATABASE_URL` en `backend/.env`, ver `.env.example`). Solo como base: la web y el ESP32 siguen pasando por el servidor. RLS activado en todas las tablas.
- [x] **Conexión a Supabase:** migraciones, seed y RLS aplicados; login, reservas y conexión del simulador andan contra la base real (20/10/2026). Se borraron las tablas y funciones del diseño viejo, y el trigger sobre `auth.users`.
- [x] **Cargar el seed nuevo en Supabase** (hecho): `python -m app.seed --reiniciar` (borra los datos de prueba que hay ahora) y reiniciar el simulador (ahora usa 32 slots).
- [x] **Terminar el ciclo con Supabase** (hecho el 21/10/2026): `retirar <codigo>` y `devolver 04A00214` en el simulador, y ver en **Table Editor → prestamo** la fila con `devuelto_en`.
- [ ] **Pasarles la conexión a tus compañeros:** la URL con la contraseña va por privado (nunca al repo). Cada uno la pone en su `backend/.env`; para desarrollar sin pisarse pueden seguir con SQLite local.
- [ ] **Configurar el `.env` de producción:** `COOKIE_SEGURA=true`, `WEB_URL` con el dominio y `SMTP_*`.

## 4. Web: lo que falta

- [ ] **Login con Google.** Hace falta crear el client ID en Google Cloud. Ahora que va a haber un dominio con HTTPS, funciona también desde los celulares.
- [x] **Decidido: la web tomó el diseño del prototipo de Joel.** Antes se evaluaba este [prototipo](https://claude.ai/artifact/BUCVFTTa6UfGr5jqzBvFh5) pasa a la web real.** Candidatos: la grilla de aulas (con 30 aulas, la lista actual es larga), la barra de la cuenta regresiva y la confirmación de retiro.
- [ ] **Mail de recuperación de verdad:** completar `SMTP_*`, por ejemplo con Gmail y una contraseña de aplicación. Mientras tanto, el link sale en la consola del servidor.

## 5. Para probar vos

Ya están hechos, pero falta tu prueba.

- [ ] **Web nueva:** recorrerla en el celular como Ana (Aulas, pedir una llave, Mis llaves, Cuenta) y como Carla (Faltantes con "Enviar recordatorio", Historial con filtros, Equipo con el cambio de tag, Docentes con alta y desactivar). Antes: `alembic upgrade head` si tu base no está al día.
- [x] **US-05** (probado el 20/10/2026): como Ana pedí una llave; en el simulador `falla <codigo>`; como Carla tiene que aparecer "Problemas del equipo hoy" con la hora, el aula y la docente. Antes: `alembic upgrade head` (tabla nueva).
- [x] **US-07:** Bruno bloqueado tras 5 intentos y desbloqueado por Carla (probado en el entorno real el 21/10/2026).
- [x] **Reiniciá tu simulador:** el que tenés abierto tiene el código viejo, sin los LEDs. Cerralo con `salir` y volvé a abrirlo.
- [x] **Fase 2 en la compu** (probado el 21/10/2026): pedir una llave como Ana, retirarla con el simulador y verla como Carla.
- [ ] **Fase 2 en el celular**, entrando a `http://<IP-de-la-compu>:5173`.
- [ ] **Sesión vencida (US-01):** sin tocar nada durante 60 s, la web vuelve sola al login; en la pantalla del código, no.
- [ ] **US-22:** `desenchufar` y `enchufar` en el simulador; los botones de la web se deshabilitan y se habilitan solos.
- [ ] **US-23 y US-24:** en el simulador, retirar y devolver una llave mirando el LED de faltantes y el LCD (`pantalla`). Frenar el backend y ver que el LED de conexión titila y no deja devolver; levantarlo de nuevo.

## 6. Fase 3: firmware

- [x] **5 llaves con UID real** (pedido del profe, 27/10/2026): 101, 102, 213, 214 y 313 en `seed/datos.json`.
- [ ] **Cargarlas en Supabase:** `python -m app.seed --reiniciar` desde `backend/` (borra los datos de prueba de la base compartida: lo corre Thiago).
- [ ] **Leer el tag HOME** (slot 0) con NFC Tools.
- [ ] **Colgar las 5 llaves** en los slots 1 a 5 (101, 102, 213, 214, 313).
- [ ] **Más adelante, los 25 llaveros que faltan** (ver `documentacion.md`, sección 4): marcarlos, leerlos con un Android con NFC Tools o con el modo diagnóstico, y cargarlos en Equipo → Tags RFID o en el seed.
- [ ] **Mosquitto para el equipo real**: hoy solo acepta conexiones de la misma compu. Para el ESP32, agregar `listener 1883` y `allow_anonymous true` a `mosquitto.conf` y abrir el puerto en el firewall (solo en desarrollo).

Lo único que falta del hardware es el motor (sección 1); lo demás ya se puede arrancar. Va un módulo por vez, cada uno con su programa de prueba:

- [ ] Proponer el mapa de pines para la NodeMCU ESP32 de 38 pines (`config.h` y `docs/cableado.md`) y esperar tu confirmación.
- [ ] LCD y scanner I2C.
- [ ] Teclado 4x4.
- [ ] Lector RFID (RC522 a **3,3 V**).
- [ ] Motor, homing y calibración.
- [ ] WiFi y MQTT, con keepalive de 10 s, LWT retenido y latido cada 30 s (ver `docs/protocolo-mqtt.md`).
- [ ] LEDs de conexión y de faltantes.
- [ ] Máquina de estados completa y modo diagnóstico (tecla `D` al encender), que lista los UID reales para el seed.

## 7. Fase 4: integración y demo

- [ ] Probar con el equipo real y medir el tiempo de un ciclo completo de retiro y devolución.
- [ ] Cambiar las contraseñas de prueba del seed (`llavetrack`) antes de la demo.

## 8. Documentación de clase y defensa

- [ ] **Avisarle a Joel qué corregir en el prototipo**, para que coincida con lo construido: código de **6 dígitos** (no 4), reserva de **2 min** (no 5), la devolución **no se pide desde la app** (tecla B en el equipo), las etiquetas "US-20" y "US-21" (ahora son US-22 a US-24) y un disco de **32 slots** (no 30).

Estos documentos los presentaste en clase y no coinciden con lo que está construido.

- [ ] **CU-01:** el sistema usa código de **6 dígitos** que vence a los **2 min** (el documento dice 4 dígitos y 5 min). La devolución **no se pide desde la app**: se toca `B` en el equipo y se cuelga la llave. El ESP32 no consulta solicitudes cada 2 s: el código lo valida el servidor por MQTT.
- [ ] **Documentos de "Servicios", "Vinculación del ESP32" y "Base de datos":** describen Supabase (API REST, polling, heartbeat por HTTP, RLS). Lo construido es FastAPI + Mosquitto, con Supabase solo como base PostgreSQL (sin su API REST: la web y el ESP32 hablan con el servidor). Hay que actualizarlos o explicar el cambio en la defensa.
- [ ] **Diagrama de bloques:**
  - Corregir "Relugador" por "Regulador".
  - Hoy el celular va directo a la Base de Datos: tiene que ir al Servidor, porque la web nunca toca la base.
  - Agregar el broker MQTT entre el ESP32 y el servidor, y los dos LEDs.
  - "Motor Paso a Paso" → "Motorreductor DC 24 V".
  - "Fuente 220/12" → "Fuente 220/16" (las flechas ya dicen 16 V).
  - El lector RFID se alimenta con 3,3 V del pin 3V3 del ESP32, no con 5 V del regulador.
  - Agregar el sensor que cuenta las pestañas del disco (entrada del ESP32).
- [ ] **Caso de uso del administrador** ("¿quién se olvidó de devolver la llave X?"): en el MVP lo resuelve la lista de aulas del preceptor (quién la tiene, desde qué hora y su teléfono). La pantalla dedicada de "sin devolver" es V2.

## Fuera del MVP (V2)

No se hace salvo que lo pidas. La lista completa está en `CLAUDE.md`: historial (US-12/13), recordatorio de devolución (US-16), devolución sin conexión (US-14), altas y bajas desde la web (US-09/10/11), entre otras.
