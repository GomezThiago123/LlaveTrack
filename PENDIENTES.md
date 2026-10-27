# Pendientes de LlaveTrack

Última actualización: 27/10/2026.

**Dónde estamos:** el servidor, la web y la base (Supabase, con las 5 llaves reales) están hechos y probados con el simulador. Lo que falta es sobre todo **el equipo** (firmware del ESP32) y **subir el servidor a la nube** para la demo. Qué es cada cosa: [documentacion.md](documentacion.md).

## 1. Ahora: probar el hardware (te toca a vos)

- [ ] **Cargar `firmware/prueba_arduino/prueba_arduino.ino`** con el Arduino IDE (placa "ESP32 Dev Module", Monitor Serie a 115200) y pegarle a Claude lo que muestre:
  - la dirección del LCD (0x27 o 0x3F);
  - si los UID que lee el lector coinciden con los de NFC Tools (ej. `Tag A94B37A4 = 101`);
  - si el teclado y el LED (`l`) andan;
  - [x] **Tiempo de vuelta del disco: 25 s** (27/10/2026), unos 0,78 s por slot.
- [ ] **Colgar el tag HOME en el slot 0** y las 5 llaves en los slots 1 a 5 (101, 102, 213, 214, 313).

## 2. Decisiones del grupo

- [ ] **LED:** hay un solo LED bicolor cableado (verde GPIO 12, rojo GPIO 15) y el diseño pedía dos (conexión y faltantes). Decidir qué muestra cada color, o cablear el segundo.
- [ ] **Motor sin control de velocidad** (ENB del L298N con jumper): ver al probar si frena justo en la llave. Si no, sacar el jumper y conectar ENB a un GPIO libre.
- [ ] **WiFi de la escuela** (decidido: el ESP32 se conecta ahí; es WPA2-Enterprise). Hace falta:
  - el nombre de la red y el método (casi siempre PEAP; lo sabe sistemas);
  - una cuenta para el equipo (mejor una de sistemas, no la personal de alguien);
  - saber si pide certificado;
  - probar que deja salir al puerto 8883: desde una notebook en esa red, MQTTX a `test.mosquitto.org:8883` con SSL. Si no conecta, plan B: hotspot de un celular.

## 3. Fase 3: firmware del equipo (Claude, después de las pruebas del punto 1)

- [ ] **Reescribir la sección Firmware del CLAUDE.md** para el motor de continua: la posición sale del lector RFID (retiro: girar hasta leer el UID pedido; lugar vacío: girar hasta no leer nada, idea del código de los compañeros, o por tiempo desde el último tag) y del tiempo de vuelta medido. Plan corto y OK antes de escribir código.
- [ ] Módulos, cada uno con su prueba: LCD → teclado → RFID → motor y búsqueda del HOME → WiFi y MQTT (keepalive 10 s, LWT, latido 30 s) → LED → máquina de estados completa → modo diagnóstico (tecla `D` al encender).
- [ ] **Mosquitto para el equipo real:** hoy solo acepta conexiones de la misma compu. Agregar `listener 1883` y `allow_anonymous true` a `mosquitto.conf` y abrir el puerto en el firewall (necesita permisos de administrador; solo en desarrollo).

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
- **Hardware relevado:** disco de 32 slots, motorreductor de continua de 24 V, placa NodeMCU ESP32 de 38 pines, LCD 16x2, tags MIFARE Classic 1K, **tag HOME `9A35EA81`**, posición por RFID (plan A) y **el cableado de los compañeros** en `docs/cableado.md`.
- **Programa de prueba del hardware** (`firmware/prueba_arduino/`), con esos pines; compila.
- **Documentación:** `documentacion.md` (para el grupo y los profes), `docs/user-stories.md`, `docs/protocolo-mqtt.md`, `docs/cableado.md`.
