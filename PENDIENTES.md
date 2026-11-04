# Pendientes de LlavesUBA

Última actualización: 05/11/2026.

**Dónde estamos:** el servidor, la web y la base (Supabase, con las 6 llaves reales) están hechos y probados con el simulador. El equipo ya entregó y recibió una llave real con el servidor en la notebook (03/11/2026). Lo que falta es terminar las pruebas del equipo y **crear las cuentas de la nube** para la demo, siguiendo [docs/despliegue.md](docs/despliegue.md). Qué es cada cosa: [documentacion.md](documentacion.md).

## 1. Ahora (te toca a vos)

- [x] **Probado con el equipo lo pedido por los superiores (05/11/2026):** entrega directa ("Pedir llave" de la 101 en la web: el equipo la sacó solo en 7 s, "Hola Ana / Aula 101") y teclado con DNI + aula ("Hola Bruno / Aula 214"; un DNI que no es de nadie dio "Credencial no reconocida"). Las devoluciones, bien.

- [x] **ESP32 conectado a la notebook Linux** con el cable de los compañeros (03/11/2026): aparece como `/dev/ttyUSB0`. Para que Linux deje usarlo sin `sudo` hizo falta una regla de udev (ver README, Firmware).
- [x] **Paso 1 del firmware probado en el equipo** (03/11/2026). Ver la sección 3.
- [x] **OK al plan de la Fase 3 y a los colores del LED** (27/10/2026): verde fijo = conectado y no falta ninguna llave; naranja = conectado y falta alguna; rojo titilando = sin conexión.
- [x] **Tags relevados y colgados** (03/11/2026): el HOME es `A94B37A4` (el `9A35EA81` anotado el 27/10 era la llave de la 104). Se sumó la **104**: quedan 6 llaves, desde el HOME 101, 104, 102, 214, 213 y 313 (slots 1 a 6; el 04/11 se recolgaron en orden: 101, 102, 104, 213, 214, 313). Seed y Supabase actualizados; los dos préstamos de prueba que habían quedado abiertos (102 y 213) se cerraron.
- [x] **LCD en 0x27** y lector OK (03/11/2026). Del programa de prueba (`firmware/prueba_arduino/`) solo faltaría ver el teclado y el LED, que se prueban igual en el paso 2.
- [x] **Tiempo de vuelta del disco: 42 a 47 s** (medido con el lector el 03/11/2026; el 25 s del 27/10 era a ojo). Unos 1,4 s por slot. El firmware la mide en cada arranque. **El 04/11 dio 24 s y el motor giraba al revés** (nadie dice haber tocado la conexión): se cambió `ADELANTE_SUMA_SLOTS` a `true`. Si vuelve a pasar, las trazas del homing lo muestran.

## 2. Decisiones del grupo

- [x] **Motor sin control de velocidad** (ENB del L298N con jumper): alcanza, porque frena con la llave centrada (03/11/2026). No hace falta sacar el jumper.
- [ ] **WiFi de la escuela** (decidido: el ESP32 se conecta ahí; es WPA2-Enterprise). Hace falta:
  - el nombre de la red y el método (casi siempre PEAP; lo sabe sistemas);
  - una cuenta para el equipo (mejor una de sistemas, no la personal de alguien);
  - saber si pide certificado;
  - probar que deja salir al puerto 8883: desde una notebook en esa red, MQTTX a `test.mosquitto.org:8883` con SSL. Si no conecta, plan B: hotspot de un celular.

## 3. Fase 3: firmware del equipo

- [x] **Plan acordado** (27/10/2026) y sección Firmware del CLAUDE.md reescrita para el motor de continua: la posición sale del lector RFID y del tiempo.
- [x] **Paso 1: el disco, sin red** (probado en el equipo el 03/11/2026; hoy es el modo diagnóstico, con D apretada al encender). Comandos del Monitor Serie: `i 5` (ir al slot 5), `b 9AAFF281 1` (buscar la 101), `v 10` (lugar vacío), `d` (qué tag hay en cada slot). Resultados:
  - el homing encuentra el HOME y mide la vuelta (42 a 47 s; la velocidad varía entre corridas y un poco dentro de la misma);
  - el lector lee los tags con el disco girando a velocidad plena (~1,4 s cada uno): no hace falta girar a pulsos;
  - el diagnóstico lista bien los 7 tags; `ADELANTE_SUMA_SLOTS = false` para el orden en que quedaron colgadas;
  - al invertir el giro el disco pierde ~0,85 slot (holgura del engranaje): `HOLGURA_REVERSA_SLOTS` lo compensa (el error bajó a ~0,15 slot);
  - `b` encuentra la llave para los dos lados (si no está donde la espera, prueba los vecinos y da la vuelta); `BUSCAR_MARGEN_SLOTS` evita que pruebe los vecinos por la deriva de medio slot;
  - `v` deja la ventana vacía.
- [x] **`b` deja la llave centrada en la ventana** (la 313, confirmado a ojo el 03/11/2026): `ADELANTO_FRENO_SLOTS` queda en 0.
- [x] **Paso 2a: la red** (probado en el equipo el 03/11/2026, con la WiFi PEINE-3 y el servidor en la notebook). Se conecta a la WiFi y al broker, manda `inicio`, el servidor le responde el lugar vacío (slot 31) y el disco va ahí; el servidor lo ve en línea; LCD en reposo con la hora; LED verde fijo. Si el servidor se cae, el LCD dice "Sin conexion / Servidor" en el mismo segundo, y cuando vuelve se recupera solo. Cómo quedó armado en la notebook:
  - Mosquitto: `/etc/mosquitto/conf.d/llavetrack.conf` con `listener 1883 0.0.0.0` y `allow_anonymous true`.
  - Firewall: `sudo ufw allow from 10.56.16.120 to any port 1883 proto tcp` (solo la IP del ESP32, porque el broker no tiene contraseña). **Si la red le da otra IP al ESP32** (la muestra el Monitor Serie al conectarse), hay que agregar la regla con la IP nueva.
  - `firmware/include/secrets.h` con PEINE-3 y la IP de la notebook (`10.56.16.125`; si cambia, actualizarla y volver a cargar el firmware).
  - La SQLite local se recargó con las 6 llaves.
- [ ] **Paso 2a, lo que falta ver:** el LED rojo titilando sin conexión, el LCD "Sin conexion / WiFi" (cortando la WiFi) y la web con el equipo real (los botones de "Pedir llave" se habilitan y deshabilitan solos).
- [x] **Paso 2b: el retiro y la devolución con el equipo real** (03/11/2026, con la web en `localhost:5173` y la base local). Retiro de la 214: código aceptado al instante, el disco la trajo en 10 s, "Aula 214 servida / RETIRE SU LLAVE", al sacarla "Gracias / Perez" y el préstamo registrado; el LCD alternó "Faltan: 214". Devolución con B: "Llave de aula / 214 recibida" y el disco fue al lugar vacío. Ciclo medido: retiro 55 s (38 s escribiendo el código, 10 s de disco, 7 s sacándola) y devolución ~10 s.
- [x] **Paso 2b, los casos que salen mal** (04/11/2026, con el equipo real): 3 códigos mal (bloqueo de 30 s con cuenta regresiva), "Llave no reconocida", "Tiempo agotado" a los 61 s, la tecla B con la llave ya colgada, "Recalibrar el disco" desde la web y US-05 (sin la llave en el disco: dos intentos, "Pedi la llave en porteria" y el incidente). La 313, la más lejana, sale en 7 s.
- [ ] **Supabase con los lugares nuevos** (04/11): 101=1, 102=2, 104=3, 213=4, 214=5, 313=6 (el seed y la base local ya están; falta correr el SQL en Supabase).
- [ ] **LED naranja (falta una llave): en pausa (04/11/2026, no es prioritario: el LCD y la web ya muestran qué falta).** El LED tiene 3 patas; verde y rojo solos andan. El firmware arma el naranja con el rojo fijo y el verde el 25% del tiempo (`NARANJA_TICKS_*` en `config.h`), y el registro de salida confirma que los pines hacen eso, pero no se ve naranja (a veces parece apagado). Falta ver la conexión: si la pata común no va a GND, el LED funciona como uno de 2 patas y no puede prender los dos colores juntos. Para retomarlo, por el Monitor Serie: `led rojo`, `led verde`, `led 1000 0` (los dos pines en alto) y `ledinfo`.

## 4. La nube, para la demo

Todo gratis, sin tarjeta y sin comprar dominio. Guía paso a paso: [docs/despliegue.md](docs/despliegue.md).

**Las cuentas y el despliegue los hacen los superiores (decidido el 04/11/2026), no el grupo.** Al grupo le toca entregarles el repo al día con la guía, pedirles los datos que necesita el equipo y probar cuando esté arriba.

- [x] **Elegir proveedores** (03/11/2026): Render (en Virginia, la región de Supabase), HiveMQ Cloud, Brevo y `*.onrender.com` como dirección con HTTPS.
- [x] **Ensayo local de la nube** (03/11/2026): la imagen de `deploy/Dockerfile` contra un Mosquitto con TLS, contraseña y permisos por equipo, con el simulador `--tls --usuario`. Anda el ciclo completo, la web desde el mismo servidor y la cookie `Secure`; el broker rechaza una clave mal, y el simulador, un certificado que no puede verificar. Falta repetirlo con los servicios reales.
- [ ] **Entregarles a los superiores** el repo al día en GitHub (Render construye desde ahí) y la guía [docs/despliegue.md](docs/despliegue.md).
- [ ] **(Superiores) Cambiar las contraseñas de prueba, antes de subir la web:** `python -m app.cambiar_clave EMAIL`. `llavetrack` figura en el repo, que es público.
- [ ] **(Superiores) Crear las cuentas:** HiveMQ (usuarios `servidor` y `equipo-01`), Brevo (remitente verificado) y Render (Blueprint). Confirmar que ninguna pida tarjeta y si HiveMQ gratis deja limitar los permisos por tópico.
- [ ] **(Superiores) Ping cada 10 min** a `/api/publico/estado` (cron-job.org). Dejarlo unas horas y confirmar que Render no se durmió.
- [ ] **Probar con el simulador contra HiveMQ** y el mail real, dando de alta a un docente con un mail de verdad.
- [ ] **Pedirles a los superiores los datos del equipo:** la dirección del cluster de HiveMQ y el usuario y la contraseña de `equipo-01` (van en `secrets.h`, nunca al repo), y la dirección de la web.
- [ ] **Placa con TLS:** `secrets.h` con HiveMQ. Nunca se probó en el equipo: es lo más incierto. Después, agregar el certificado de la CA.
- [ ] **Probar que la WiFi deja salir por el 8883.**
- [ ] **Medir un ciclo completo** de retiro y devolución con el equipo real contra la nube.
- [ ] **Probar el plan B:** todo en una compu con el hotspot de un celular.
- [ ] **Pasarles la conexión de Supabase** solo a quien la necesite, por privado (nunca al repo). Para desarrollar sin pisarse, cada uno puede usar SQLite local.

## 5. Pruebas de la web que te tocan

- [ ] **Recorrer la web en el celular** (`http://<IP-de-la-compu>:5173`) como Ana y como Carla.
- [ ] **US-01:** sin tocar nada 60 s, la web vuelve al login; en la pantalla del código, no.
- [ ] **US-22:** `desenchufar` y `enchufar` en el simulador; los botones de la web se deshabilitan y se habilitan solos.
- [ ] **US-23 y US-24:** en el simulador, retirar y devolver mirando el LED de faltantes y el LCD (`pantalla`); frenar el servidor y ver que el LED de conexión titila.

## 6. Fase 4: integración y demo

- [ ] Probar con el equipo real y medir el tiempo de un ciclo completo de retiro y devolución.

### Problemas encontrados al revisar el código (03/11/2026, arreglados el 04/11/2026)

- [x] **Retiro que no se registra:** si sacaban la llave en los últimos 1,5 s antes de los 60 s, se mandaba `retiro_timeout` y no `retiro_confirmado`. Ahora, si la llave ya no se ve, primero se confirma el retiro. Cargado y probado el 04/11.
- [x] **La sesión podía vencer con el celular bloqueado:** ahora el servidor no da por vencida la sesión de alguien con una reserva pendiente (vigente). Cuando retira la llave o la reserva vence, vuelve la regla de los 60 s.
- [x] **`recalibrar` no existía en el servidor:** ahora el preceptor tiene el botón "Recalibrar el disco" en la pantalla Equipo (`POST /api/equipo/recalibrar`). Probado con el equipo real el 04/11.

## 7. Defensa y documentos de clase

- [ ] **Mandarle a Joel las correcciones del prototipo:** código de 6 dígitos (no 4), reserva de 2 min (no 5), la devolución no se pide desde la app (tecla B), US-22 a US-24 (no "US-20/21") y disco de 32 slots (no 30).
- [ ] **CU-01:** código de 6 dígitos que vence a los 2 min; la devolución es con la tecla B en el equipo; el código lo valida el servidor por MQTT (el ESP32 no consulta cada 2 s).
- [ ] **Documentos de "Servicios", "Vinculación del ESP32" y "Base de datos":** describen Supabase como API. Lo construido es FastAPI + Mosquitto, con Supabase solo como base.
- [ ] **Diagrama de bloques:** "Regulador" (dice "Relugador"); el celular va al servidor, no a la base; agregar el broker MQTT; "Motorreductor DC 24 V" (no paso a paso); "Fuente 220/16" (no 12); lector RFID a 3,3 V del ESP32 (no 5 V); un LED bicolor; la posición del disco la da el lector RFID (no hay sensor extra).

## 8. V2: todas hechas (04/11/2026)

Servidor y web probados con tests (190). Las que tocan el equipo están escritas en el firmware y compilan, pero **falta probarlas con el equipo real**:

- [x] **US-18, retiro con DNI:** probado el 05/11 con DNI + aula en el teclado.
- [ ] **US-20, devolver una llave de otro:** B, el DNI de otro docente y #, colgar la llave. "Retirada por Perez #=OK", # y "recibida". Al que la tenía le llega un mail, y en Mis llaves dice "La devolvió...".
- [ ] **US-15, corte de luz:** pedir una llave, A + código + #, y cortar la luz mientras gira. Al volver: "Equipo listo" y la reserva cancelada en la web.
- [ ] **US-14, devolver sin conexión:** frenar el servidor (o Mosquitto), B y colgar la llave: "Sin conexion / Devol. guardada" y el disco busca otro lugar vacío. Al volver el servidor, la devolución aparece en la web con la hora real.
- [ ] **US-10, modo alta:** en Equipo, "Dar de alta una llave", acercar un tag al lector, elegir el aula en la web y guardar.
- [ ] **El simulador** (`backend/simulador/`) todavía no tiene los eventos nuevos (DNI, `retiro_interrumpido`, `tag_leido`). No hace falta para la demo.
- [ ] **Supabase:** las migraciones nuevas (incidentes resueltos, bajas, hora fin, DNI) se aplican solas al desplegar (`alembic upgrade head` en el Dockerfile). Si se usa Supabase antes, correr `alembic upgrade head` con su `DATABASE_URL`.

---

## Hecho (resumen; el detalle está en el historial de git)

- **Fases 0, 1 y 2:** servidor, base, MQTT, simulador y web, con 139 tests. MVP completo con el simulador: US-01, 02, 03, 07, 08, 22; US-04, 05, 06, 23 y 24 del lado del servidor y el simulador.
- **V2 hechas a pedido:** US-09 (docentes), US-10 (tags RFID a mano), US-12/13 (historial), US-16 (recordatorio manual), US-17 (mis llaves).
- **Decisiones sobre las user stories** (20/10): sesión de 60 s, reserva de 2 min, todos ven quién tiene cada llave, devolución automática, incidentes para el preceptor, desbloqueo manual, textos de los criterios. US-22 a US-24 cargadas en Notion.
- **Web rediseñada** con el prototipo de Joel y los colores de la UBA (21/10), probada con capturas y contra Supabase.
- **Supabase:** migraciones con RLS en todas las tablas, las listas sin una consulta por fila, y **las 6 llaves reales cargadas** (101, 102, 104, 213, 214, 313 en los slots 1 a 6; recolgadas el 04/11). El proyecto queda con esas 6 llaves (las 5 del profe del 27/10 más la 104); `seed/datos_30_aulas.json` queda solo como referencia.
- **Web:** los grupos de aulas se llaman "Peine 1/2/3" (27/10/2026).
- **Hardware relevado:** disco de 32 slots (una vuelta: entre 24 y 47 s según el día), motorreductor de continua de 24 V, placa NodeMCU ESP32 de 38 pines, LCD 16x2 en 0x27, tags MIFARE Classic 1K, **tag HOME `A94B37A4`**, posición por RFID (plan A) y **el cableado de los compañeros** en `docs/cableado.md`.
- **Programa de prueba del hardware** (`firmware/prueba_arduino/`), con esos pines; compila.
- **Documentación:** `documentacion.md` (para el grupo y los profes), `docs/user-stories.md`, `docs/protocolo-mqtt.md`, `docs/cableado.md`.
