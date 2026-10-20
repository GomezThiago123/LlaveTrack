# Pendientes de LlaveTrack

Última actualización: 20/10/2026. Hechas hasta ahora: Fase 0, Fase 1, Fase 2 (salvo Google), US-20, US-21 y US-22 en el servidor y el simulador, la base en Supabase y el seed con las 30 aulas.

## 1. Respuestas que necesito de vos

Bloquean trabajo: sin estas respuestas no se puede seguir con lo que dice cada una.

- [ ] **Decisiones sobre las user stories** (sección 2b): lo construido no coincide con algunos criterios de aceptación.
- [ ] **Motor:** modelo, cantidad de cables, tensión nominal y reducción (mirar la etiqueta). En las fotos parece un motorreductor de 2 cables y no un paso a paso: si es así, hace falta un sensor que cuente las pestañas del disco. *Bloquea: la Fase 3 (motor).*
- [ ] **LEDs:** dos bicolores (conexión y faltantes). En la Fase 3 propongo los colores, GPIO y resistencias.
- [ ] **Proveedor de la nube** para el servidor (ver la sección 3). Lo propongo yo cuando lleguemos.
- [ ] **WiFi para la demo:** la de la escuela es WPA2-Enterprise. ¿Router propio o hotspot del celular? El ESP32 puede conectarse a WPA2-Enterprise, pero necesita una cuenta de la escuela guardada en el equipo y la red puede bloquear el puerto 8883.

### Ya respondidas (20/10/2026)

- **Disco:** 32 slots. El 0 es del tag HOME, así que quedan 31 lugares: entran las 30 aulas y sobra 1.
- **Aula 105:** el asterisco era un error; es un aula como las demás.
- **Placa:** NodeMCU ESP32 de 38 pines con USB-C (módulo ESP-WROOM-32).
- **LCD:** 16x2. La dirección I2C sale del scanner en la Fase 3.
- **Referencia de cero:** el tag RFID HOME en el slot 0, por ahora.
- **Servidor de la demo:** en la nube.
- **Seed con las 30 aulas:** OK.
- **User stories:** recibidas y guardadas en `docs/user-stories.md`.
- **WiFi de la escuela:** WPA2-Enterprise.
- **LEDs:** dos bicolores, uno por agujero del panel.

## 2. Lo próximo en el código

En el orden acordado. Cada uno arranca con un plan corto y espera tu OK.

- [x] **US-21: LED y LCD de llaves faltantes.** Hecho en el servidor y el simulador; en el equipo se hace en la Fase 3.
- [x] **US-22: LED de conexión con el servidor.** Hecho en el servidor y el simulador (el LED titila mientras no hay conexión); en el equipo se hace en la Fase 3.
- [x] **Seed con las 30 aulas reales** (101–105, 111–115, 201–205, 211–215, 301–305, 311–315): `slotsTotales: 32`, slot 0 para HOME, aulas en los slots 1 a 30 y UID inventados (`04A0` + aula, ej. `04A00214`) hasta el modo diagnóstico. El simulador usa `--slots 32` por defecto. Los tests usan sus propios datos (`tests/datos_prueba.json`) y un test valida el seed real.
- [x] **Documentación de US-20 a US-22:** tópicos nuevos (`latido`, `faltantes`, `servidor/estado`), `EQUIPO_TIMEOUT_SEGUNDOS` y reglas de los LEDs en el CLAUDE.md, `docs/protocolo-mqtt.md` y el README.
- [x] **Revisar lo construido contra los criterios de aceptación.** Las diferencias están en la sección 2b.

## 2b. Diferencias con las user stories (`docs/user-stories.md`)

Esperan tu decisión. Después armo un plan y espero tu OK.

- [ ] **Numeración:** en Notion, US-20 es "Devolver una llave retirada por otro" y US-21 es "Registrar incidentes" (las dos V2). En el código y en los commits, US-20/21/22 son equipo desconectado, LED de faltantes y LED de conexión, y no figuran en Notion. Propuesta: cargarlas en Notion como US-22, US-23 y US-24 y renombrarlas en el código y en la documentación (los commits viejos quedan como están).
- [ ] **US-01, sesión de 60 s** (hoy 15 min). Decidido: 60 s, salvo mientras está abierta la pantalla del código. Falta implementarlo.
- [ ] **US-02, quién ve quién tiene la llave:** decidido: todos los usuarios logueados ven nombre, hora y teléfono (hoy solo el preceptor y el admin). Falta implementarlo.
- [ ] **US-03, la reserva vence a los 2 min:** decidido: 2 min por defecto (hoy 10). Falta implementarlo; acordate de borrar `RESERVA_MINUTOS=3` de tu `.env`.
- [ ] **US-05, incidente visible para el preceptor** después de 2 fallas seguidas. Hoy el evento `error` se guarda, pero nadie lo ve. La sección "Incidentes" completa es US-21 (V2): ¿qué parte entra en el MVP?
- [ ] **US-06, "cuando confirmo":** ¿el docente aprieta `#` para confirmar la devolución, o alcanza con colgar la llave (como ahora)?
- [x] **US-07, desbloqueo manual por el preceptor:** cuadro "Cuentas bloqueadas" en la lista de aulas del preceptor y el admin.
- [ ] **Textos exactos de los criterios:** "Usuario o contraseña incorrectos" (hoy "Email o…"), "Ocupada" (hoy "Prestada"), "Cuenta bloqueada temporalmente", "Si el email está registrado, te enviamos un link", y en el LCD "Aula X servida / RETIRE SU LLAVE", "Gracias X" al retirar, "Reposicionando...", "Pedi la llave / en porteria" y "Llave de aula X recibida" (todo de 16 caracteres por línea y sin tildes).

## 3. El servidor en la nube

Como la demo corre en la nube, hay cosas nuevas para resolver antes de la Fase 4:

- [ ] **Elegir proveedor:** tiene que poder correr el servidor de Python **y** Mosquitto, que necesita un puerto TCP propio. Los hostings que solo sirven páginas web no alcanzan.
- [ ] **Dominio con HTTPS** para la web y la API.
- [ ] **Mosquitto expuesto a internet:** TLS en el puerto 8883, usuario y contraseña por equipo y una ACL por prefijo. Nunca el 1883 abierto. El ESP32 se conecta con `WiFiClientSecure` y el certificado raíz.
- [x] **Base persistente:** PostgreSQL de Supabase (`DATABASE_URL` en `backend/.env`, ver `.env.example`). Solo como base: la web y el ESP32 siguen pasando por el servidor. RLS activado en todas las tablas.
- [x] **Conexión a Supabase:** migraciones, seed y RLS aplicados; login, reservas y conexión del simulador andan contra la base real (20/10/2026). Se borraron las tablas y funciones del diseño viejo, y el trigger sobre `auth.users`.
- [ ] **Cargar el seed nuevo en Supabase:** `python -m app.seed --reiniciar` (borra los datos de prueba que hay ahora) y reiniciar el simulador (ahora usa 32 slots).
- [ ] **Terminar el ciclo con Supabase:** `retirar <codigo>` y `devolver 04A00214` en el simulador, y ver en **Table Editor → prestamo** la fila con `devuelto_en`.
- [ ] **Pasarles la conexión a tus compañeros:** la URL con la contraseña va por privado (nunca al repo). Cada uno la pone en su `backend/.env`; para desarrollar sin pisarse pueden seguir con SQLite local.
- [ ] **Configurar el `.env` de producción:** `COOKIE_SEGURA=true`, `WEB_URL` con el dominio y `SMTP_*`.

## 4. Web: lo que falta

- [ ] **Login con Google.** Hace falta crear el client ID en Google Cloud. Ahora que va a haber un dominio con HTTPS, funciona también desde los celulares.
- [ ] **Decidir qué parte del [prototipo](https://claude.ai/artifact/BUCVFTTa6UfGr5jqzBvFh5) pasa a la web real.** Candidatos: la grilla de aulas (con 30 aulas, la lista actual es larga), la barra de la cuenta regresiva y la confirmación de retiro.
- [ ] **Mail de recuperación de verdad:** completar `SMTP_*`, por ejemplo con Gmail y una contraseña de aplicación. Mientras tanto, el link sale en la consola del servidor.

## 5. Para probar vos

Ya están hechos, pero falta tu prueba.

- [ ] **Reiniciá tu simulador:** el que tenés abierto tiene el código viejo, sin los LEDs. Cerralo con `salir` y volvé a abrirlo.
- [ ] **Fase 2 en la compu:** pedir una llave como Ana, retirarla con el simulador y verla como Carla.
- [ ] **Fase 2 en el celular**, entrando a `http://<IP-de-la-compu>:5173`.
- [ ] **Sesión vencida (US-01):** sin tocar nada durante 60 s, la web vuelve sola al login; en la pantalla del código, no.
- [ ] **US-20:** `desenchufar` y `enchufar` en el simulador; los botones de la web se deshabilitan y se habilitan solos.
- [ ] **US-21 y US-22:** en el simulador, retirar y devolver una llave mirando el LED de faltantes y el LCD (`pantalla`). Frenar el backend y ver que el LED de conexión titila y no deja devolver; levantarlo de nuevo.

## 6. Fase 3: firmware

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

Estos documentos los presentaste en clase y no coinciden con lo que está construido.

- [ ] **CU-01:** el sistema usa código de **6 dígitos** que vence a los **2 min** (el documento dice 4 dígitos y 5 min). La devolución **no se pide desde la app**: se toca `B` en el equipo y se cuelga la llave. El ESP32 no consulta solicitudes cada 2 s: el código lo valida el servidor por MQTT.
- [ ] **Documentos de "Servicios", "Vinculación del ESP32" y "Base de datos":** describen Supabase (API REST, polling, heartbeat por HTTP, RLS). Lo construido es FastAPI + Mosquitto, con Supabase solo como base PostgreSQL (sin su API REST: la web y el ESP32 hablan con el servidor). Hay que actualizarlos o explicar el cambio en la defensa.
- [ ] **Diagrama de bloques:**
  - Corregir "Relugador" por "Regulador".
  - Hoy el celular va directo a la Base de Datos: tiene que ir al Servidor, porque la web nunca toca la base.
  - Agregar el broker MQTT entre el ESP32 y el servidor, y los dos LEDs.
- [ ] **Caso de uso del administrador** ("¿quién se olvidó de devolver la llave X?"): en el MVP lo resuelve la lista de aulas del preceptor (quién la tiene, desde qué hora y su teléfono). La pantalla dedicada de "sin devolver" es V2.

## Fuera del MVP (V2)

No se hace salvo que lo pidas. La lista completa está en `CLAUDE.md`: historial (US-12/13), recordatorio de devolución (US-16), devolución sin conexión (US-14), altas y bajas desde la web (US-09/10/11), entre otras.
