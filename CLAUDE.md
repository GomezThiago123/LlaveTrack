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

## Arquitectura
```
Web (React, mobile-first) ──HTTPS / REST JSON──► Servidor (Node + TS) ◄──► Base de datos
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
- `server/`: Node.js LTS + TypeScript, Express, mqtt.js, Prisma (SQLite en desarrollo, se puede pasar a PostgreSQL después), zod para validar todo lo que entra (REST y MQTT), Vitest.
- `web/`: React + Vite + TypeScript, pensada para usar desde el celular. Sin app nativa en el MVP.
- Broker: Mosquitto local (ya instalado); inspecciono los mensajes con MQTTX.
- `tools/simulador/`: CLI que se hace pasar por el ESP32 vía MQTT (ingresar código, confirmar retiro, devolver un UID). Para desarrollar y testear sin hardware.
- `docs/`: `protocolo-mqtt.md` (contrato) y `cableado.md` (pines y alimentación).

## Modelo de datos (MVP)
- `Usuario`: nombre, apellido, email (único), telefono, rol (`DOCENTE` | `PRECEPTOR` | `ADMIN`), activo, más los campos de auth que correspondan (ver Autenticación).
- `Aula`: nombre (ej. "214"). Una llave por aula en el MVP.
- `Llave`: aulaId, rfidUid (único; hex en mayúsculas sin separadores, ej. `04A1B2C3`), slot (posición actual en el disco, puede cambiar), estado (`DISPONIBLE` | `RESERVADA` | `PRESTADA` | `BAJA`).
- `Reserva`: usuarioId, llaveId, codigo (6 dígitos, único entre las pendientes), expiraEn, estado (`PENDIENTE` | `USADA` | `VENCIDA` | `CANCELADA`).
- `Prestamo`: llaveId, usuarioId, reservaId, retiradoEn, devueltoEn (null = activo).
- `Dispositivo`: deviceId, slots totales y reservados, online, ultimoContacto.
- `EventoDispositivo`: eventId (único), tipo, payload, recibidoEn. Sirve de log y para descartar duplicados.

Reglas:
- Una llave nunca puede quedar tomada dos veces: cada cambio de estado es un UPDATE condicional (`where: { id, estado: 'DISPONIBLE' }`) dentro de una transacción, verificando cuántas filas cambió. Test obligatorio con dos pedidos simultáneos.
- Un docente tiene como máximo una reserva pendiente.
- Fechas en UTC en la base; se muestran en `America/Argentina/Buenos_Aires`.
- Seed desde un archivo editable (aulas, llaves con UID y slot, usuarios), porque el alta desde la web es V2.

## API REST (web ↔ servidor)
- `GET /api/publico/estado`: sin login. Aulas con su estado y si el equipo está online. Sin datos personales.
- `GET /api/aulas`: con login. Quién tiene cada llave y su teléfono, solo visible para `PRECEPTOR`/`ADMIN`.
- `POST /api/reservas` `{ aulaId }` → `{ codigo, expiraEn }` · `GET /api/reservas/activa` · `DELETE /api/reservas/:id`.
- Errores: `{ "error": { "codigo": "LLAVE_NO_DISPONIBLE", "mensaje": "..." } }`.

## Flujos del MVP
### Retiro (US-02 a US-05)
1. El docente ve las aulas y pide una. El servidor reserva la llave y devuelve un código de 6 dígitos que vence en 10 min. La web lo muestra grande con cuenta regresiva (también si recarga la página).
2. En el equipo: tecla `A`, ingresa el código (`*` borra, `#` confirma). 3 códigos erróneos seguidos bloquean el teclado 30 s.
3. ESP32 → `solicitud_retiro`. El servidor valida y responde `slot`, `uid`, `aula`, `apellido`, o un `motivo` de rechazo.
4. El ESP32 mueve el disco a ese slot y verifica que lee ESE UID. Si no: prueba ±1 slot; si tampoco, da una vuelta completa buscándolo. Si no aparece: error en el LCD y no entrega nada.
5. LCD "Retire la llave". Cuando ese UID deja de leerse de forma estable (~1,5 s) → `retiro_confirmado`, con el slot donde estaba realmente. El servidor marca la reserva `USADA`, la llave `PRESTADA` y crea el `Prestamo`. La ventana queda con un slot vacío (posición de reposo).
6. Si nadie la retira en 60 s → `retiro_timeout` y el disco vuelve a dejar un slot vacío en la ventana. La reserva sigue vigente hasta que vence.
7. Reservas vencidas → `VENCIDA` y la llave vuelve a `DISPONIBLE`.

### Devolución (US-06)
En reposo siempre hay un slot vacío frente a la ventana. El RFID no puede "buscar" un lugar vacío (el tag está en la mano del docente), por eso el sistema tiene que conocer la posición del disco.
1. Tecla `B` → LCD "Cuelgue la llave". El docente la cuelga en el slot de la ventana.
2. Al leer un UID estable (~1 s) → `devolucion { uid, slot }`. El servidor cierra el préstamo activo de esa llave (queda asociado al docente que la retiró), la pasa a `DISPONIBLE`, actualiza su `slot` y responde aula, apellido y `slotReposo` (otro slot vacío).
3. El LCD confirma y el disco gira a `slotReposo`.
4. UID desconocido o sin préstamo activo: "Llave no reconocida" y no se registra nada.

### Autenticación (US-01, US-07, US-08): DECIDIDO, las dos opciones
El usuario elige en la pantalla de login: email + contraseña o "Ingresar con Google". Las dos entran al mismo `Usuario`, identificado por su email.
- Email + contraseña (se implementa primero): hash bcrypt (`bcryptjs` no necesita compilar nada en Windows), bloqueo de 15 min tras 5 intentos fallidos (US-07) y recuperación por email (nodemailer + SMTP) con link que vence en 30 min (US-08). `passwordHash` puede ser null (usuario que solo entra con Google).
- Google (se agrega después): la web obtiene el ID token, el servidor lo verifica (audience = client ID, email verificado) y solo deja entrar emails cargados en `Usuario` con `activo = true`; nunca crea usuarios. Guardar `googleSub` la primera vez. En desarrollo funciona en `http://localhost`; para usarlo desde celulares en la demo hace falta un dominio con HTTPS (Google no acepta IPs tipo 192.168.x.x): deploy o túnel. Si no hay, la demo usa contraseña.
- En las dos: sesión en cookie httpOnly que se cierra tras 15 min de inactividad (US-01).

## Protocolo MQTT (ESP32 ↔ servidor)
- Prefijo `llavetrack/v1/{deviceId}/`. El ESP32 publica en `evt/{tipo}` y en `estado` (retenido, con LWT `{"online":false}`); se suscribe a `resp` y `cmd`.
- Eventos: `inicio` (informa su configuración de slots; el servidor responde `slotReposo`), `solicitud_retiro`, `retiro_confirmado`, `retiro_timeout`, `devolucion`, `error`. Comando del MVP: `recalibrar`.
- Cada evento lleva un `eventId` único aunque el ESP32 se reinicie (ej. `equipo-01-<random de arranque>-<contador>`). El servidor responde cada evento en `resp` con el mismo `eventId` y `ok: true`, o `ok: false` + `motivo` (`CODIGO_INVALIDO`, `CODIGO_VENCIDO`, `LLAVE_DESCONOCIDA`, `SIN_PRESTAMO_ACTIVO`, `ERROR_INTERNO`).
- PubSubClient solo publica con QoS 0, así que la confiabilidad es de aplicación: el ESP32 reintenta el mismo evento hasta recibir respuesta y el servidor descarta duplicados por `eventId`. Sin respuesta en 5 s → LCD "Sin respuesta" y reintento.
- `client.setBufferSize(512)`: el buffer por defecto (256 bytes) corta los JSON.
- Mosquitto: en desarrollo, anónimo en localhost; para la demo, usuario y contraseña por equipo y una ACL que limite cada equipo a su prefijo.

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
- Modo diagnóstico (mantener `D` al encender): UIDs por Serial y LCD, escaneo del bus I2C y una vuelta al disco listando qué UID hay en cada slot (sirve para armar el seed).

## Hardware y cableado (→ `docs/cableado.md` y `config.h`)
- Alimentación: fuente 220 V → 16 V DC (el diagrama de bloques dice 12 V por error) → interruptor + fusible en la línea de 16 V → step-up a 24 V para el motor (vía L298N) y step-down a 5 V para el ESP32 (pin 5V/VIN) y el LCD. GND común a todo.
- RC522: 3,3 V desde el pin 3V3 del ESP32. Nunca 5 V (el diagrama lo muestra a 5 V: está mal) ni 24 V.
- L298N a 24 V: sacar el jumper del regulador de 5 V del módulo y alimentar su lógica con 5 V externos. No limita corriente: la tensión tiene que ser la nominal del motor.
- LCD I2C: dirección 0x27 o 0x3F (confirmar con el scanner). Si el adaptador va a 5 V, sus pull-ups ponen 5 V en SDA/SCL del ESP32 (que es de 3,3 V): usar un adaptador de nivel.
- Pines ESP32: no usar 6–11 (flash). Cuidado con los de arranque 0, 2, 12 y 15 (12 nunca con pull-up externo). 34–39 son solo entrada y sin pull-up interno (sirven para el sensor de cero con pull-up externo). I2C en 21/22; SPI en 18/19/23 con SS en 5. El teclado 4x4 usa 8 pines: si no alcanzan, va en un PCF8574 sobre el mismo bus I2C.
- Proponé el mapa de pines (`config.h` + tabla en `docs/cableado.md`) y esperá mi confirmación antes de usarlo.

## Pendientes (preguntame antes de asumir)
- [x] Autenticación: las dos (email + contraseña primero, Google después). Ver "Autenticación".
- [ ] Motor: en las fotos parece un motorreductor de 2 cables, no un paso a paso. Confirmar con la etiqueta antes de la Fase 3.
- [ ] Motor: modelo, cantidad de cables, tensión nominal y reducción. Asumido: paso a paso bipolar de 4 cables. Si es un motor DC, frená y avisame: sin pasos que contar hace falta un sensor que cuente las pestañas del disco.
- [ ] Modelo exacto de la placa ESP32.
- [ ] LCD: 16x2 (asumido) y su dirección I2C.
- [ ] Referencia de cero: qué sensor, o el tag HOME provisorio.
- [ ] Cantidad de slots del disco y de llaves para la demo.
- [ ] Dónde corre el servidor en la demo (notebook en la misma red o nube). Ver si el WiFi de la escuela tiene portal cautivo o WPA2-Enterprise: si es así, usar el router propio del diagrama o un hotspot.

## Fases
0. Esqueleto: estructura del repo, README con cómo levantar todo, `.gitignore`, ejemplos de `.env` y `secrets.h`, `docs/protocolo-mqtt.md` y borrador de `docs/cableado.md`.
1. Servidor + base + MQTT + simulador: modelo, migraciones, seed, reglas de reserva y préstamo con tests (concurrencia, vencimiento, eventos duplicados). Termina cuando el ciclo retiro → devolución anda completo con el simulador y Mosquitto.
2. Web: vista pública de disponibilidad, login, lista de aulas con refresco cada 5 s, pedir llave con código y cuenta regresiva, estado del equipo.
3. Firmware por módulos, cada uno con su programa de prueba: LCD + scanner I2C → teclado → RFID → motor + homing + calibración → WiFi/MQTT → máquina de estados completa.
4. Integración con el equipo real y pruebas de usabilidad (medir el tiempo del ciclo retiro + devolución).

## Fuera del MVP (V2: no implementar salvo que lo pida)
US-09 registrar docentes · US-10 dar de alta una llave · US-11 dar de baja una llave perdida · US-12/13 historial por aula y por docente · US-14 devolver sin conexión · US-15 corte de luz durante un retiro · US-16 recordatorio de devolución · US-17 ver mis llaves · US-18 retiro con credencial · US-19 exportar reportes a Excel.

Sin cerrarles la puerta: `eventId` únicos (sirven para sincronizar offline), roles ya presentes en `Usuario`, todos los movimientos con fecha y hora, y guardar los cambios online/offline del equipo (métrica de disponibilidad del Lean Canvas).
