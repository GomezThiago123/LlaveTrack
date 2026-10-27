# LlaveTrack — contexto del proyecto para Claude Code

## Qué es
Sistema para retirar y devolver las llaves de las aulas de la ETEC-UBA. Las llaves cuelgan de un disco giratorio de MDF y cada una tiene un tag RFID (13,56 MHz). El docente reserva la llave desde una web, va al equipo, ingresa un código en el teclado, el disco gira hasta dejar su llave en la ventana de entrega y el sistema registra quién la retiró y a qué hora. Al devolverla, el lector RFID la reconoce y cierra el préstamo.

Proyecto escolar (metodologías ágiles + IoT). Prioridades: que funcione en la demo, que sea simple y que yo (Thiago) pueda explicar cada parte en la defensa.

## Cómo trabajar conmigo
- Hablame en español. Trabajamos por fases (ver "Fases"): antes de escribir código de una fase, mostrame un plan corto (archivos, pasos, cómo se prueba) y esperá mi OK. Al terminar, decime exactamente qué tengo que probar yo y cómo.
- No inventes datos de hardware (motor, pines, tensiones, dirección I2C). Si falta algo, preguntame. Revisá "Pendientes" antes de cada fase.
- No podés ver el hardware: en firmware compilá con `pio run` y pedime que lo suba y te pegue la salida del monitor serie. Que compile no significa que funcione.
- Código claro antes que ingenioso, con comentarios en español donde no sea obvio.
- Dominio en español y sin tildes en identificadores (`prestamo`, `aula`, `llave`). Textos de la UI en español rioplatense.
- Desarrollo en Windows 11 y Linux Mint: scripts multiplataforma (nada exclusivo de bash).
- Commits chicos que nombren la historia: `US-03: reserva con vencimiento`.
- Secretos fuera del repo: `.env` y `firmware/include/secrets.h` en `.gitignore`, con `.env.example` y `secrets.example.h`.
- Tiempos y límites siempre configurables (`.env` / `config.h`); los valores de este archivo son iniciales.
- Si cambia una decisión, actualizá este archivo y `docs/`.
- Al terminar cada historia, actualizá `PENDIENTES.md` **y** `documentacion.md` (qué es, cómo funciona, estado de cada US y decisiones, escrito para el grupo y los profes; no repite el README ni este archivo).

## Arquitectura
```
Web (React, mobile-first) ──HTTPS / REST JSON──► Servidor (Python)    ◄──► Base de datos
                                                       ▲
                                                       │ MQTT (Mosquitto)
                                                       ▼
                ESP32 + RC522 + LCD 16x2 I2C + teclado 4x4 + motor vía L298N
```
- El servidor es la única fuente de verdad. Las horas de retiro y devolución las pone el servidor, no el ESP32.
- La web nunca habla con el ESP32 y el ESP32 nunca toca la base: todo pasa por el servidor.
- El ESP32 no decide reglas de negocio: pide permiso, mueve el disco, lee tags e informa.

## Stack
- `firmware/`: ESP32 con framework Arduino sobre PlatformIO (extensión de VS Code + CLI `pio`, para compilar desde la terminal). Librerías: MFRC522, LiquidCrystal_I2C, Keypad, AccelStepper, PubSubClient, ArduinoJson 7.
- `backend/`: Python 3.11+ con FastAPI (sincrónico, sin `async`), SQLAlchemy + Alembic (SQLite en desarrollo; PostgreSQL de Supabase para la demo y la base compartida, vía `DATABASE_URL` con el Session pooler y el driver `psycopg`. Supabase es solo la base: no se usa su API, su Auth ni su cliente JS, y toda tabla nueva activa RLS sin políticas en su migración para que la API de Supabase no la exponga), paho-mqtt corriendo en su propio hilo, Pydantic para validar todo lo que entra (REST y MQTT), pytest. Entorno virtual propio en `backend/.venv` con `backend/requirements.txt` (versiones fijas). Se corre desde `backend/` con el `.venv` activado: `python run.py` (puerto 8000), `pytest`. Los tests ignoran el `.env` (`LLAVETRACK_TESTS=1` en `conftest.py`) y cargan `tests/datos_prueba.json`, no el seed real.
- `backend/` y `frontend/` son independientes: cada uno se instala y se levanta en su propia terminal, sin nada compartido en la raíz.
- `frontend/`: React + Vite + TypeScript, pensada para usar desde el celular. Sin app nativa en el MVP. Se corre desde `frontend/`: `npm install`, `npm run dev` (puerto 5173; Vite reenvía `/api` al backend en :8000, u otro con `LLAVETRACK_API`). Node 20.19+ (recomendado 24). Diseño: el [prototipo de Joel](https://github.com/joel012930/llavetrack) (v0) pasado a CSS común con los colores de la UBA (azul, celeste y blanco); íconos con `lucide-react` (versión fija). Barra de abajo: el docente tiene Aulas · Mis llaves · Cuenta; el preceptor y el admin, Aulas · Faltantes · Historial · Equipo · Docentes (y Cuenta arriba). El código de la reserva se muestra arriba de la lista de aulas.
- Broker: Mosquitto local (ya instalado); inspecciono los mensajes con MQTTX.
- `backend/simulador/`: CLI interactiva en Python (usa el `.venv` del backend) que se hace pasar por el ESP32 vía MQTT: queda prendida con LWT y latido, y en su prompt se puede retirar, devolver, `desenchufar` (corte de luz) y `enchufar`. Para desarrollar y testear sin hardware.
- `docs/`: `protocolo-mqtt.md` (contrato), `cableado.md` (pines y alimentación) y `user-stories.md` (las de Notion con sus criterios de aceptación: revisarlas antes de cada historia).

## Modelo de datos (MVP)
- `Usuario`: nombre, apellido, email (único), telefono, rol (`DOCENTE` | `PRECEPTOR` | `ADMIN`), activo, más los campos de auth que correspondan (ver Autenticación).
- `Aula`: nombre (ej. "214"). Una llave por aula en el MVP.
- `Llave`: aulaId, rfidUid (único; hex en mayúsculas sin separadores, ej. `04A1B2C3`), slot (posición actual en el disco, puede cambiar), estado (`DISPONIBLE` | `RESERVADA` | `PRESTADA` | `BAJA`).
- `Reserva`: usuarioId, llaveId, codigo (6 dígitos, único entre las pendientes), expiraEn, estado (`PENDIENTE` | `USADA` | `VENCIDA` | `CANCELADA`).
- `Prestamo`: llaveId, usuarioId, reservaId, retiradoEn, devueltoEn (null = activo), recordatorioEnviadoEn (US-16).
- `Dispositivo`: deviceId, slots totales y reservados, online, ultimoContacto.
- `EventoDispositivo`: eventId (único), tipo, payload, recibidoEn. Sirve de log y para descartar duplicados.
- `Incidente` (US-05): deviceId, tipo (`LLAVE_NO_ENCONTRADA`, `MOTOR_NO_GIRA`), detalle, aulaId y usuarioId (de la reserva, si el equipo mandó el código), ocurridoEn. Lo crea cada evento `error`. Resolverlos es US-21 (V2): agregar `resueltoEn`.

Reglas:
- Una llave nunca puede quedar tomada dos veces: cada cambio de estado es un UPDATE condicional (`UPDATE llave SET estado = ... WHERE id = ? AND estado = 'DISPONIBLE'`, con SQLAlchemy) dentro de una transacción, verificando cuántas filas cambió. Test obligatorio con dos pedidos simultáneos.
- Un docente tiene como máximo una reserva pendiente.
- Fechas en UTC en la base; se muestran en `America/Argentina/Buenos_Aires`.
- Seed desde un archivo editable (`backend/seed/datos.json`): por pedido del profe (27/10/2026) son 5 llaves con sus UID reales (101, 102, 213, 214 y 313 en los slots 1 a 5) y los usuarios de prueba. Las 30 aulas, con UID inventados, quedan en `seed/datos_30_aulas.json` para más adelante.
- Vencimiento "perezoso": antes de cada consulta o cambio (REST o MQTT) se llama `vencer_reservas()`. No hay tarea periódica.
- `Llave.slot` es null mientras la llave está prestada (no está en el disco).
- La lógica va en `app/servicios/` (sin commit); las rutas HTTP y el cliente MQTT llaman a esos servicios y hacen el commit.
- SQLite abre cada transacción con `BEGIN IMMEDIATE` (pedidos simultáneos en fila): toda sesión tiene que cerrarse rápido (una por pedido HTTP o por evento MQTT).
- Eventos MQTT: `app/protocolo.py` valida, deduplica y responde; las reglas están en `app/servicios/equipo.py`. El evento se procesa dentro de un savepoint: si se rechaza se deshace solo lo del evento (el vencimiento de reservas se conserva).
- Al aceptar un código, la reserva se extiende al menos `RETIRO_MARGEN_SEGUNDOS` (120) para que no venza durante el retiro.
- `slotReposo` = slot vacío más cercano (disco circular) a la posición actual; vacíos = todos − reservados − slots con llave.
- Sesiones en la tabla `Sesion` (token al azar en la cookie, solo su hash sha256 en la base; igual los links de `RecuperacionClave`). `usuario_actual` (`app/auth.py`) lee la cookie `llavetrack_sesion` y renueva la sesión en cada pedido. El login fallido igual hace commit (para que cuente el intento).

## API REST (web ↔ servidor)
- `GET /api/publico/estado`: sin login. Aulas con su estado y si el equipo está online. Sin datos personales.
- `GET /api/aulas`: con login. Quién tiene cada llave, desde qué hora y su teléfono, visible para todos los usuarios logueados (US-02, decidido el 20/10/2026).
- `POST /api/reservas` `{ aulaId }` → `{ codigo, expiraEn }` · `GET /api/reservas/activa` · `GET /api/reservas/:id` (cualquier estado: la web ve si ya se retiró) · `DELETE /api/reservas/:id`.
- Login: `POST /api/auth/login` `{ email, clave }` · `POST /api/auth/logout` · `GET /api/auth/yo` · `POST /api/auth/recuperar` `{ email }` · `POST /api/auth/restablecer` `{ token, claveNueva }`.
- `GET /api/prestamos/mios` (US-17): con login, los préstamos propios (primero los abiertos).
- Solo `PRECEPTOR`/`ADMIN` (si no, 403 `SIN_PERMISO`): `GET /api/usuarios/bloqueados` · `POST /api/usuarios/:id/desbloquear` (US-07) · `GET /api/incidentes` (US-05: los de hoy, hora de Argentina) · `GET /api/prestamos?aulaId&usuarioId&desde&hasta&estado` (US-12/13; fechas = días de Argentina; trae `enPoder` si se filtra por docente) · `POST /api/prestamos/:id/recordatorio` (US-16, mail) · `GET /api/usuarios` · `POST /api/usuarios` (US-09: alta de docente con mail para crear la clave, link de `ALTA_LINK_HORAS`) · `PATCH /api/usuarios/:id` `{ activo }` (desactivar cierra sus sesiones) · `GET /api/equipo` · `PUT /api/llaves/:id/rfid` (US-10). Los cuadros "Problemas del equipo hoy" y "Cuentas bloqueadas" aparecen arriba de la lista de aulas del preceptor y en sus pantallas Equipo y Docentes.
- La web manda `X-Refresco-Automatico: 1` en los pedidos que hace sola cada 5 s: no renuevan la sesión (si no, con la web abierta nunca vencería por inactividad). Excepción: la pantalla del código no lo manda, así la sesión no se cierra mientras el docente va al equipo (la reserva igual vence sola).
- Errores: `{ "error": { "codigo": "LLAVE_NO_DISPONIBLE", "mensaje": "..." } }`.

## Flujos del MVP
### Retiro (US-02 a US-05)
1. El docente ve las aulas y pide una. El servidor reserva la llave y devuelve un código de 6 dígitos que vence en 2 min (US-03). La web lo muestra grande con cuenta regresiva (también si recarga la página).
2. En el equipo: tecla `A`, ingresa el código (`*` borra, `#` confirma). 3 códigos erróneos seguidos bloquean el teclado 30 s.
3. ESP32 → `solicitud_retiro`. El servidor valida y responde `slot`, `uid`, `aula`, `apellido`, o un `motivo` de rechazo.
4. El ESP32 mueve el disco a ese slot y verifica que lee ESE UID. Si no: prueba ±1 slot; si tampoco, da una vuelta completa buscándolo. Intento 1: el slot y sus vecinos; intento 2: homing de nuevo y otra búsqueda. Mientras reintenta, LCD "Reposicionando" / "Espere..." ("Reposicionando..." tiene 17 caracteres). Si no aparece: LCD "Pedi la llave" / "en porteria", no entrega nada y manda `error` `LLAVE_NO_ENCONTRADA` con el código (US-05).
5. LCD "Aula 214 servida" / "RETIRE SU LLAVE" (US-04). Cuando ese UID deja de leerse de forma estable (~1,5 s) → `retiro_confirmado`, con el slot donde estaba realmente. El servidor marca la reserva `USADA`, la llave `PRESTADA` y crea el `Prestamo`. LCD "Gracias" / apellido. La ventana queda con un slot vacío (posición de reposo).
6. Si nadie la retira en 60 s → `retiro_timeout` y el disco vuelve a dejar un slot vacío en la ventana. La reserva sigue vigente hasta que vence.
7. Reservas vencidas → `VENCIDA` y la llave vuelve a `DISPONIBLE`.

### Devolución (US-06)
En reposo siempre hay un slot vacío frente a la ventana. El RFID no puede "buscar" un lugar vacío (el tag está en la mano del docente), por eso el sistema tiene que conocer la posición del disco.
1. Tecla `B` → LCD "Cuelgue la llave". El docente la cuelga en el slot de la ventana.
2. Al leer un UID estable (~1 s) → `devolucion { uid, slot }`. El servidor cierra el préstamo activo de esa llave (queda asociado al docente que la retiró), la pasa a `DISPONIBLE`, actualiza su `slot` y responde aula, apellido y `slotReposo` (otro slot vacío).
3. LCD "Llave de aula" / "214 recibida" (US-06) y el disco gira a `slotReposo`. La devolución se confirma sola al leer el UID: el docente no aprieta nada (decidido el 20/10/2026).
4. UID desconocido o sin préstamo activo: "Llave no reconocida" y no se registra nada.

### Autenticación (US-01, US-07, US-08): DECIDIDO, las dos opciones
El usuario elige en la pantalla de login: email + contraseña o "Ingresar con Google". Las dos entran al mismo `Usuario`, identificado por su email.
- Email + contraseña (se implementa primero): hash con `bcrypt`, bloqueo de 15 min tras 5 intentos fallidos (US-07) y recuperación por email (`smtplib` de la librería estándar) con link que vence en 30 min (US-08). `passwordHash` puede ser null (usuario que solo entra con Google).
- Google (se agrega después): la web obtiene el ID token, el servidor lo verifica con `google-auth` (audience = client ID, email verificado) y solo deja entrar emails cargados en `Usuario` con `activo = true`; nunca crea usuarios. Guardar `googleSub` la primera vez. En desarrollo funciona en `http://localhost`; para usarlo desde celulares en la demo hace falta un dominio con HTTPS (Google no acepta IPs tipo 192.168.x.x): deploy o túnel. Si no hay, la demo usa contraseña.
- En las dos: sesión en cookie httpOnly que se cierra tras 60 s de inactividad (US-01), salvo mientras está abierta la pantalla del código.

## Protocolo MQTT (ESP32 ↔ servidor)
- Prefijo `llavetrack/v1/{deviceId}/`. El ESP32 publica en `evt/{tipo}`, en `estado` (retenido, con LWT `{"online":false}` también retenido) y en `latido` (`{}` cada 30 s, sin eventId ni respuesta); se suscribe a `resp`, `cmd`, `faltantes` y `llavetrack/v1/servidor/estado`.
- Equipo online (US-22, `app/servicios/conexion.py`): último `estado` online **y** contacto (evento o latido) hace menos de `EQUIPO_TIMEOUT_SEGUNDOS` (90). El servidor marca todos offline al conectarse y al desconectarse del broker; al suscribirse recupera el `estado` retenido. Keepalive del ESP32: 10 s (el broker publica el LWT a los ~15 s). Sin equipo online, `POST /api/reservas` → 409 `EQUIPO_DESCONECTADO`; una reserva PENDIENTE no se cancela si el equipo se cae (vence sola).
- Servidor vivo (US-24): el servidor publica `llavetrack/v1/servidor/estado` retenido (`{"online":true}` al conectar, `false` al apagarse, LWT `false`). `servidor` es un deviceId reservado (el servidor ignora su propio estado en `+/estado`). LED de conexión del equipo: fijo si WiFi + broker + servidor online; si no, titila y el LCD dice "Sin conexion" con la causa (`WiFi`, `Broker`, `Servidor`). La ACL de cada equipo incluye lectura de ese tópico.
- Faltantes (US-23): el servidor publica `faltantes` retenido `{"aulas":[...]}` con las llaves PRESTADAS (las reservadas siguen en el disco), al cambiar, al responder `inicio` y al conectarse al broker. El equipo prende el LED de faltantes y en reposo rota la línea 1 del LCD entre la hora y "Faltan: 105 114" (regla en `pantallas_reposo()` del simulador).
- Eventos: `inicio` (informa su configuración de slots; el servidor responde `slotReposo`), `solicitud_retiro`, `retiro_confirmado`, `retiro_timeout`, `devolucion`, `error` (con el `codigo` de la reserva si lo hay: crea un `Incidente`). Comando del MVP: `recalibrar`.
- Cada evento lleva un `eventId` único aunque el ESP32 se reinicie (ej. `equipo-01-<random de arranque>-<contador>`). El servidor responde cada evento en `resp` con el mismo `eventId` y `ok: true`, o `ok: false` + `motivo` (`CODIGO_INVALIDO`, `CODIGO_VENCIDO`, `LLAVE_DESCONOCIDA`, `SIN_PRESTAMO_ACTIVO`, `ERROR_INTERNO`).
- PubSubClient solo publica con QoS 0, así que la confiabilidad es de aplicación: el ESP32 reintenta el mismo evento hasta recibir respuesta y el servidor descarta duplicados por `eventId`. Sin respuesta en 5 s → LCD "Sin respuesta" y reintento.
- `client.setBufferSize(512)`: el buffer por defecto (256 bytes) corta los JSON.
- Mosquitto: en desarrollo, anónimo en localhost. En la demo el servidor está en la nube, así que el broker queda expuesto a internet: TLS (puerto 8883, `WiFiClientSecure` en el ESP32), usuario y contraseña por equipo y una ACL que limite cada equipo a su prefijo. Nunca el 1883 abierto.

```
llavetrack/v1/equipo-01/evt/solicitud_retiro
  {"eventId":"equipo-01-7f3a-0042","codigo":"482913"}
llavetrack/v1/equipo-01/resp
  {"eventId":"equipo-01-7f3a-0042","ok":true,"slot":7,"uid":"04A1B2C3","aula":"214","apellido":"Perez"}
```

## Firmware
- Módulos: `config.h` (pines y constantes), `secrets.h`, `lcd`, `teclado`, `rfid`, `motor`, `red` (WiFi + MQTT con reconexión), `protocolo` (JSON) y `main.cpp` con la máquina de estados.
- Nada bloqueante: `millis()` en lugar de `delay()` largos y `stepper.run()` en cada vuelta del `loop()`. Estados: `INICIO → HOMING → REPOSO → INGRESO_CODIGO → ESPERANDO_SERVIDOR → MOVIENDO → ESPERANDO_RETIRO | ESPERANDO_DEVOLUCION → REPOSO`, más `ERROR` con mensaje en el LCD.
- Posición (asumiendo motor paso a paso): homing contra una referencia de cero al arrancar y después contar pasos; `slot = round(pasos / PASOS_POR_SLOT)`. Rutina de calibración que mida `PASOS_POR_VUELTA` entre dos pasadas por el cero. Repetir el homing si falla una verificación de UID.
- Referencia de cero: sensor (final de carrera, óptico o hall) en un GPIO. Mientras no esté montado, un tag RFID "HOME" fijo en un slot reservado que nunca se asigna a una llave (tomar como posición el centro entre el paso donde empieza a leerse y donde deja de leerse).
- Bobinas energizadas mientras el usuario manipula el disco (para que no se corra al tirar de la llave) y apagadas en reposo (el L298N calienta). Por eso cada entrega verifica el UID.
- RFID: comparar siempre contra el UID esperado, nunca contra "cualquier tag" (el lector puede ver tags vecinos). `PICC_IsNewCardPresent()` no sirve para saber si un tag sigue ahí: usar `PICC_WakeupA()` o lectura repetida.
- LCD 16x2: máximo 16 caracteres por línea y sin tildes ni ñ (el juego de caracteres del HD44780 no es español). Una función `lcdMensaje(linea1, linea2)` que recorte. En reposo: hora (NTP, TZ `<-03>3`) y "A:Retirar B:Dev."
- Teclas: `A` retirar, `B` devolver, `C` cancelar, `*` borrar, `#` confirmar.
- Sin conexión el equipo no entrega ni recibe llaves (LCD "Sin conexion"). La devolución offline es V2 (US-14).
- MQTT: `client.setKeepAlive(10)`, LWT retenido (`willRetain = true` en `connect()`), `estado` `{"online":true}` retenido al conectar y `latido` cada 30 s (`MQTT_KEEPALIVE_S` y `LATIDO_S` en `config.h`).
- Modo diagnóstico (mantener `D` al encender): UIDs por Serial y LCD, escaneo del bus I2C y una vuelta al disco listando qué UID hay en cada slot (sirve para armar el seed).

## Hardware y cableado (→ `docs/cableado.md` y `config.h`)
- Alimentación: fuente 220 V → 16 V DC (el diagrama de bloques dice 12 V por error) → interruptor + fusible en la línea de 16 V → step-up a 24 V para el motor (vía L298N) y step-down a 5 V para el ESP32 (pin 5V/VIN) y el LCD. GND común a todo.
- RC522: 3,3 V desde el pin 3V3 del ESP32. Nunca 5 V (el diagrama lo muestra a 5 V: está mal) ni 24 V.
- L298N a 24 V: sacar el jumper del regulador de 5 V del módulo y alimentar su lógica con 5 V externos. No limita corriente: la tensión tiene que ser la nominal del motor.
- LCD I2C: dirección 0x27 o 0x3F (confirmar con el scanner). Si el adaptador va a 5 V, sus pull-ups ponen 5 V en SDA/SCL del ESP32 (que es de 3,3 V): usar un adaptador de nivel.
- Pines ESP32: no usar 6–11 (flash). Cuidado con los de arranque 0, 2, 12 y 15 (12 nunca con pull-up externo). 34–39 son solo entrada y sin pull-up interno (sirven para el sensor de cero con pull-up externo). I2C en 21/22; SPI en 18/19/23 con SS en 5. El teclado 4x4 usa 8 pines: si no alcanzan, va en un PCF8574 sobre el mismo bus I2C.
- Proponé el mapa de pines (`config.h` + tabla en `docs/cableado.md`) y esperá mi confirmación antes de usarlo.

## Pendientes (preguntame antes de asumir)
Lista completa de tareas y preguntas abiertas: `PENDIENTES.md` (mantenela al día al terminar cada historia). Las user stories con sus criterios están en `docs/user-stories.md`; US-22 a US-24 se agregaron al MVP el 20/10/2026 (en los commits viejos figuran como US-20 a US-22).
- [x] Autenticación: las dos (email + contraseña primero, Google después). Ver "Autenticación".
- [x] Motor: motorreductor de continua (DC), 24 V y 2 cables (respuesta del 20/10/2026), no un paso a paso aunque lo diga el diagrama de bloques. Va por un canal del L298N a 24 V (coincide con su tensión nominal).
- [ ] Sensor de posición: ¿hay un sensor para contar las 32 pestañas del disco o hay que conseguirlo (sin pasos que contar, la posición sale de ahí). La sección Firmware → Posición todavía describe el paso a paso: se reescribe cuando esté confirmado. Bloquea la Fase 3 (motor).
- [ ] Motor: modelo, cantidad de cables, tensión nominal y reducción. Asumido: paso a paso bipolar de 4 cables. Si es un motor DC, frená y avisame: sin pasos que contar hace falta un sensor que cuente las pestañas del disco.
- [x] Placa: NodeMCU ESP32 de 38 pines con USB-C (módulo ESP-WROOM-32). Los pines 6–11 están expuestos pero son de la flash: no usarlos.
- [x] LCD: 16x2 confirmado.
- [ ] LCD: dirección I2C (0x27 o 0x3F), sale del scanner en la Fase 3.
- [x] Referencia de cero: tag RFID HOME en el slot 0 por ahora (sin sensor). Su UID es `9A35EA81` (leído el 27/10/2026): va en `config.h` como `UID_HOME`, no en la base.
- [x] Disco de 32 slots. El 0 es del tag HOME: quedan 31 lugares, entran las 30 aulas reales y sobra 1.
- [ ] LEDs: dos bicolores, uno por agujero del panel: conexión y faltantes (respuesta del 20/10/2026). Falta: qué color significa qué, GPIO y resistencias. Se decide en la Fase 3: proponerlos (`config.h` + `docs/cableado.md`) y esperar confirmación.
- [x] Aula 105: el asterisco era un error; es un aula como las demás.
- [x] El servidor de la demo corre en la nube. Pendiente: proveedor, dominio con HTTPS, Mosquitto accesible desde internet con TLS, (ver `PENDIENTES.md`). Base persistente: Supabase (proyecto `njdagfhwhtppqpypagzx`).
- [ ] WiFi: el ESP32 se conecta a la WiFi de la escuela, que es WPA2-Enterprise (decidido el 20/10/2026). El módulo `red` usa WPA2-Enterprise (PEAP) con usuario y contraseña en `secrets.h`. Falta: nombre de la red, método (casi siempre PEAP), una cuenta para el equipo (mejor una que dé sistemas, no la personal de alguien), si pide certificado, y probar que la red deja salir al puerto 8883. Plan B: hotspot de un celular.

## Fases
0. Esqueleto: estructura del repo, README con cómo levantar todo, `.gitignore`, ejemplos de `.env` y `secrets.h`, `docs/protocolo-mqtt.md` y borrador de `docs/cableado.md`.
1. Servidor + base + MQTT + simulador: modelo, migraciones, seed, reglas de reserva y préstamo con tests (concurrencia, vencimiento, eventos duplicados). Termina cuando el ciclo retiro → devolución anda completo con el simulador y Mosquitto.
2. Web: vista pública de disponibilidad, login, lista de aulas con refresco cada 5 s, pedir llave con código y cuenta regresiva, estado del equipo. Con el equipo desconectado, "Pedir llave" queda deshabilitado ("Equipo desconectado") y se reactiva solo con el refresco (US-22).
3. Firmware por módulos, cada uno con su programa de prueba: LCD + scanner I2C → teclado → RFID → motor + homing + calibración → WiFi/MQTT → máquina de estados completa.
4. Integración con el equipo real y pruebas de usabilidad (medir el tiempo del ciclo retiro + devolución).

## Fuera del MVP (V2: no implementar salvo que lo pida)
Ya hechas, a pedido (20/10/2026): US-09 alta y desactivar docentes · US-10 cambiar el tag RFID (UID a mano hasta el "modo alta" del equipo) · US-12/13 historial · US-16 recordatorio (lo manda el preceptor: el sistema no conoce los turnos) · US-17 mis llaves.

Pendientes: US-11 dar de baja una llave perdida · US-14 devolver sin conexión · US-15 corte de luz durante un retiro · US-18 retiro con credencial · US-19 exportar reportes a Excel · US-20 devolver una llave retirada por otro · US-21 registrar incidentes (del MVP solo entra lo que pide US-05: que el preceptor vea las fallas).

Sin cerrarles la puerta: `eventId` únicos (sirven para sincronizar offline), roles ya presentes en `Usuario`, todos los movimientos con fecha y hora, y guardar los cambios online/offline del equipo (métrica de disponibilidad del Lean Canvas).
