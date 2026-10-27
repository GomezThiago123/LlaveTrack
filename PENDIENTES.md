# Pendientes de LlaveTrack

Última actualización: 27/10/2026.

**Dónde estamos:** el servidor, la web y la base (Supabase, con las 5 llaves reales) están hechos y probados con el simulador. Lo que falta es sobre todo **el equipo** (firmware del ESP32) y **subir el servidor a la nube** para la demo. Qué es cada cosa: [documentacion.md](documentacion.md).

## 1. Ahora (te toca a vos)

- [ ] **Conectar el ESP32 a la compu con un cable que pase datos.** Es lo que traba todo el firmware: sin eso no se le puede cargar ningún programa.
  - El driver del chip USB de la placa (**CP210x** de Silicon Labs) ya está instalado: la placa apareció una vez como **COM5** (27/10/2026).
  - Pero la conexión se cortó y después Windows no registró nada al volver a enchufarla: el cable no pasa datos o el conector está flojo. Probar **el cable con el que los compañeros cargaron su programa** u otro puerto, y no moverlo una vez conectado.
  - **Plan B:** Claude arma el firmware en un archivo y se carga desde la compu de los compañeros con Chrome (página de Espressif, sin instalar nada).
  - Hoy el ESP32 tiene el programa de los compañeros ("Ingrese aula"), que solo conoce los UID de la 214 y la 313: por eso con 101 dice que no la encuentra.
- [ ] **Probar el paso 1 del firmware** cuando la placa conecte: Claude lo carga y lee el Monitor Serie desde la compu (hay que estar al lado: el disco gira solo al arrancar). Ver la sección 3.
- [x] **OK al plan de la Fase 3 y a los colores del LED** (27/10/2026): verde fijo = conectado y no falta ninguna llave; naranja = conectado y falta alguna; rojo titilando = sin conexión.
- [ ] **Colgar el tag HOME en el slot 0** y las 5 llaves en los slots 1 a 5 (101, 102, 213, 214, 313).
- [ ] **Si podés, pasar la salida del programa de prueba** (`firmware/prueba_arduino/`): la dirección del LCD, si los UID del lector coinciden con los de NFC Tools y si andan el teclado y el LED. No traba nada: el firmware busca solo la dirección del LCD, y cada módulo se prueba igual en la Fase 3.
- [x] **Tiempo de vuelta del disco: 25 s** (27/10/2026), unos 0,78 s por slot.

## 2. Decisiones del grupo

- [ ] **Motor sin control de velocidad** (ENB del L298N con jumper): ver al probar si frena justo en la llave. Si no, sacar el jumper y conectar ENB a un GPIO libre.
- [ ] **WiFi de la escuela** (decidido: el ESP32 se conecta ahí; es WPA2-Enterprise). Hace falta:
  - el nombre de la red y el método (casi siempre PEAP; lo sabe sistemas);
  - una cuenta para el equipo (mejor una de sistemas, no la personal de alguien);
  - saber si pide certificado;
  - probar que deja salir al puerto 8883: desde una notebook en esa red, MQTTX a `test.mosquitto.org:8883` con SSL. Si no conecta, plan B: hotspot de un celular.

## 3. Fase 3: firmware del equipo

- [x] **Plan acordado** (27/10/2026) y sección Firmware del CLAUDE.md reescrita para el motor de continua: la posición sale del lector RFID y del tiempo.
- [ ] **Paso 1: el disco, sin red** (`firmware/`, escrito y compila con `pio run`; falta cargarlo: ver el punto 1). Al prender busca el HOME y mide la vuelta; después, desde el Monitor Serie: `i 5` (ir al slot 5), `b A94B37A4 1` (buscar la 101), `v 31` (lugar vacío), `d` (diagnóstico: qué tag hay en cada slot). Hay que probar:
  - que el homing encuentre el HOME y mida unos 25 s;
  - el diagnóstico: que la 101 aparezca en el slot 1, la 102 en el 2, etc. Si aparecen al revés (la 101 en el 31), cambiar `ADELANTE_SUMA_SLOTS` en `config.h`;
  - que `b` frene con la llave centrada en la ventana (si se pasa, ajustar `ADELANTO_FRENO_SLOTS`);
  - que `v` deje un lugar vacío en la ventana.
  - Si el lector no ve los tags con el disco girando (los compañeros movían de a pulsos), avisar: se agrega el giro a pulsos.
- [ ] **Paso 2: WiFi, MQTT y el retiro y la devolución completos** (reemplaza al simulador). Antes: **Mosquitto para el equipo real** (hoy solo acepta conexiones de la misma compu: agregar `listener 1883` y `allow_anonymous true` a `mosquitto.conf` y abrir el puerto en el firewall; necesita permisos de administrador) y la red WiFi (`secrets.h`).

## 4. La nube, para la demo

- [ ] **Elegir proveedor:** tiene que correr Python **y** Mosquitto (puerto TCP propio). **En la misma región que Supabase (us-east-1, Virginia):** desde Argentina cada consulta tarda ~170 ms y un evento del equipo puede tardar 2–5 s; en la misma región, milisegundos.
- [ ] **Dominio con HTTPS** para la web y la API.
- [ ] **Mosquitto expuesto a internet:** TLS en el 8883, usuario y contraseña por equipo, ACL por prefijo. Nunca el 1883 abierto.
- [ ] **`.env` de producción:** `COOKIE_SEGURA=true`, `WEB_URL` con el dominio y `SMTP_*`.
- [ ] **Mail de verdad** (SMTP, por ejemplo Gmail con contraseña de aplicación). Hoy los mails salen en la consola del servidor.
- [ ] **Login con Google** (client ID en Google Cloud; anda con el dominio).
- [ ] **Pasarles la conexión de Supabase a los compañeros**, por privado (nunca al repo). Para desarrollar sin pisarse, cada uno puede usar SQLite local.

## 5. Pruebas de la web que te tocan

- [ ] **Recorrer la web en el celular** (`http://<IP-de-la-compu>:5173`) como Ana y como Carla.
- [ ] **US-01:** sin tocar nada 60 s, la web vuelve al login; en la pantalla del código, no.
- [ ] **US-22:** `desenchufar` y `enchufar` en el simulador; los botones de la web se deshabilitan y se habilitan solos.
- [ ] **US-23 y US-24:** en el simulador, retirar y devolver mirando el LED de faltantes y el LCD (`pantalla`); frenar el servidor y ver que el LED de conexión titila.

## 6. Fase 4: integración y demo

- [ ] Probar con el equipo real y medir el tiempo de un ciclo completo de retiro y devolución.
- [ ] Cambiar las contraseñas de prueba (`llavetrack`) antes de la demo.

## 7. Defensa y documentos de clase

- [ ] **Mandarle a Joel las correcciones del prototipo:** código de 6 dígitos (no 4), reserva de 2 min (no 5), la devolución no se pide desde la app (tecla B), US-22 a US-24 (no "US-20/21") y disco de 32 slots (no 30).
- [ ] **CU-01:** código de 6 dígitos que vence a los 2 min; la devolución es con la tecla B en el equipo; el código lo valida el servidor por MQTT (el ESP32 no consulta cada 2 s).
- [ ] **Documentos de "Servicios", "Vinculación del ESP32" y "Base de datos":** describen Supabase como API. Lo construido es FastAPI + Mosquitto, con Supabase solo como base.
- [ ] **Diagrama de bloques:** "Regulador" (dice "Relugador"); el celular va al servidor, no a la base; agregar el broker MQTT; "Motorreductor DC 24 V" (no paso a paso); "Fuente 220/16" (no 12); lector RFID a 3,3 V del ESP32 (no 5 V); un LED bicolor; la posición del disco la da el lector RFID (no hay sensor extra).

## 8. V2 que no se hicieron

US-11 (baja de llave perdida) · US-14 (devolver sin conexión) · US-15 (corte de luz durante un retiro) · US-18 (retiro con credencial) · US-19 (exportar a Excel) · US-20 (devolver una llave de otro) · US-21 (marcar incidentes como resueltos).

---

## Hecho (resumen; el detalle está en el historial de git)

- **Fases 0, 1 y 2:** servidor, base, MQTT, simulador y web, con 129 tests. MVP completo con el simulador: US-01, 02, 03, 07, 08, 22; US-04, 05, 06, 23 y 24 del lado del servidor y el simulador.
- **V2 hechas a pedido:** US-09 (docentes), US-10 (tags RFID a mano), US-12/13 (historial), US-16 (recordatorio manual), US-17 (mis llaves).
- **Decisiones sobre las user stories** (20/10): sesión de 60 s, reserva de 2 min, todos ven quién tiene cada llave, devolución automática, incidentes para el preceptor, desbloqueo manual, textos de los criterios. US-22 a US-24 cargadas en Notion.
- **Web rediseñada** con el prototipo de Joel y los colores de la UBA (21/10), probada con capturas y contra Supabase.
- **Supabase:** migraciones con RLS en todas las tablas, las listas sin una consulta por fila, y **las 5 llaves reales cargadas** (101, 102, 213, 214, 313; 27/10). El proyecto queda con esas 5 llaves (decidido el 27/10/2026); `seed/datos_30_aulas.json` queda solo como referencia.
- **Web:** los grupos de aulas se llaman "Peine 1/2/3" (27/10/2026).
- **Hardware relevado:** disco de 32 slots (una vuelta: 25 s), motorreductor de continua de 24 V, placa NodeMCU ESP32 de 38 pines, LCD 16x2, tags MIFARE Classic 1K, **tag HOME `9A35EA81`**, posición por RFID (plan A) y **el cableado de los compañeros** en `docs/cableado.md`.
- **Programa de prueba del hardware** (`firmware/prueba_arduino/`), con esos pines; compila.
- **Documentación:** `documentacion.md` (para el grupo y los profes), `docs/user-stories.md`, `docs/protocolo-mqtt.md`, `docs/cableado.md`.
