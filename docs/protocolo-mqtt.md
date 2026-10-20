# Protocolo MQTT (ESP32 ↔ servidor)

Contrato entre el equipo (ESP32) y el servidor. El simulador (`backend/simulador`) usa este mismo contrato, así que todo lo que funcione con el simulador tiene que funcionar con el equipo real.

> Versión `v1`, implementada en la Fase 1 (`backend/app/protocolo.py`, `backend/app/servicios/equipo.py`).

## Reglas generales

- El servidor es la única fuente de verdad: decide si se entrega una llave y pone todas las horas. Los mensajes del ESP32 **no llevan fecha ni hora**.
- Todos los mensajes son JSON en UTF-8.
- Los UID RFID van en hexadecimal, en mayúsculas y sin separadores (ej. `04A1B2C3`).
- Los slots se numeran desde 0 (el slot 0 es la posición de homing).
- PubSubClient solo publica con QoS 0, por eso la confiabilidad se resuelve en la aplicación (ver [Reintentos y duplicados](#reintentos-y-duplicados)).
- El ESP32 usa `client.setBufferSize(512)`, porque con el buffer por defecto de 256 bytes los JSON se cortan.

## Tópicos

Prefijo: `llavetrack/v1/{deviceId}/` (ej. `llavetrack/v1/equipo-01/`).

| Tópico | Quién publica | Retenido | Para qué |
| --- | --- | --- | --- |
| `evt/{tipo}` | ESP32 | no | Eventos (ver abajo) |
| `estado` | ESP32 | **sí** | `{"online":true}` al conectar. LWT: `{"online":false}` |
| `latido` | ESP32 | no | `{}` cada 30 s: "sigo vivo" (ver [Conexión del equipo](#conexión-del-equipo)) |
| `resp` | servidor | no | Respuesta a cada evento, con el mismo `eventId` |
| `faltantes` | servidor | **sí** | Aulas cuya llave no está en el disco (ver [Llaves faltantes](#llaves-faltantes-us-21)) |

El servidor publica además su propio estado, fuera del prefijo de los equipos:

| Tópico | Quién publica | Retenido | Para qué |
| --- | --- | --- | --- |
| `llavetrack/v1/servidor/estado` | servidor | **sí** | `{"online":true}` al conectar. LWT: `{"online":false}` (ver [LED de conexión](#led-de-conexión-us-22)) |

`servidor` es un deviceId **reservado**: como `servidor/estado` coincide con el patrón `+/estado` de los equipos, el servidor ignora ese nombre. Ningún equipo puede llamarse así.
| `cmd` | servidor | no | Comandos al equipo |

## Conexión del equipo

El servidor considera **online** a un equipo solo si se cumplen las dos cosas:

1. Su último mensaje de `estado` dice `{"online":true}`.
2. Tuvo contacto (cualquier evento o un `latido`) hace menos de `EQUIPO_TIMEOUT_SEGUNDOS` (90 s por defecto: 3 latidos perdidos).

Con el equipo desconectado, la web no deja pedir llaves: `POST /api/reservas` responde `409 EQUIPO_DESCONECTADO` (US-22). Una reserva que ya estaba pendiente no se cancela: vence sola y, si el equipo vuelve antes, el código sirve.

| Situación | Qué pasa | En cuánto se entera el servidor |
| --- | --- | --- |
| El equipo se corta (luz, WiFi, cuelgue) | El broker no recibe más pings y publica el LWT `{"online":false}` (retenido) | ~15 s (1,5 × keepalive de 10 s) |
| El equipo se apaga prolijo | Publica `{"online":false}` antes de desconectarse | Enseguida |
| El servidor pierde el broker | Marca todos los equipos offline: sin broker no puede saber nada de ellos | Enseguida (keepalive del servidor: 15 s) |
| Se reinicia el servidor | Al conectarse marca todos offline y se suscribe a `estado`: el broker le manda el último mensaje retenido de cada equipo | Enseguida |
| Quedó retenido un `{"online":true}` viejo (ej. Mosquitto con persistencia y el equipo muerto) | Sin latidos, vence el contacto | `EQUIPO_TIMEOUT_SEGUNDOS` |

Del lado del ESP32 (PubSubClient):

```cpp
client.setKeepAlive(MQTT_KEEPALIVE_S);            // 10 s (por defecto son 15)
client.connect(clientId, usuario, clave,
               topicoEstado, 1, true,             // LWT con QoS 1 y retenido
               "{\"online\":false}");
client.publish(topicoEstado, "{\"online\":true}", true);   // retenido
// y cada LATIDO_S (30 s): client.publish(topicoLatido, "{}");
```

El `latido` no lleva `eventId`, no tiene respuesta y no se guarda en el log de eventos (`EventoDispositivo`): solo actualiza el último contacto del equipo.

## Llaves faltantes (US-23)

El servidor publica en `faltantes` (retenido, QoS 1) la lista de aulas cuya llave está **PRESTADA**, ordenada por nombre:

```json
llavetrack/v1/equipo-01/faltantes  {"aulas":["105","204"]}
llavetrack/v1/equipo-01/faltantes  {"aulas":[]}
```

- Las llaves RESERVADAS no cuentan: siguen colgadas en el disco hasta que el docente las retira. Por eso el vencimiento de una reserva no cambia la lista.
- Se publica cuando la lista cambia (después de `retiro_confirmado` o `devolucion`), al responder `inicio` y cada vez que el servidor se conecta al broker. Como es retenida, el equipo la recibe sola al suscribirse.
- Con las 30 aulas son unos 200 bytes: entra en el buffer de 512.

Qué hace el equipo con la lista:

- **LED de faltantes** encendido si la lista no está vacía.
- **LCD en reposo:** la línea 2 queda fija (`A:Retirar B:Dev.`) y la línea 1 rota cada `LCD_ROTACION_MS` (3 s) entre la hora y las aulas que faltan, con todas las que entren en 16 caracteres. Un nombre que no entra ni solo va en su propia pantalla, recortado a 16. Sin faltantes, solo la hora. La regla está implementada en `pantallas_reposo()` del simulador, con tests:

```
[Mar 20/10  14:32]   [Faltan: 105 114 ]   [Faltan: 204     ]
[A:Retirar B:Dev.]   [A:Retirar B:Dev.]   [A:Retirar B:Dev.]
```

## LED de conexión (US-24)

El equipo sabe que el servidor está vivo por `llavetrack/v1/servidor/estado` (retenido):

- El servidor publica `{"online":true}` al conectarse al broker y `{"online":false}` antes de apagarse prolijo.
- Si se cae sin despedirse, el broker publica su LWT `{"online":false}` en ~22 s (1,5 × keepalive de 15 s).
- Como es retenido, el equipo lo recibe al suscribirse. Conviene suscribirse a este tópico **antes** que a `faltantes`, así el estado del servidor llega primero.

| WiFi | Broker | Servidor | LED de conexión | LCD | Entrega y recibe llaves |
| --- | --- | --- | --- | --- | --- |
| sí | sí | online | encendido fijo | reposo normal | sí |
| sí | sí | offline | titila | `Sin conexion` / `Servidor` | no |
| sí | no | — | titila | `Sin conexion` / `Broker` | no |
| no | — | — | titila | `Sin conexion` / `WiFi` | no |

Titila (en vez de apagarse) para distinguir "prendido pero sin conexión" de "sin luz". El equipo reintenta solo en todos los casos.

**ACL de Mosquitto:** cada equipo necesita, además de su prefijo, permiso de **lectura** sobre `llavetrack/v1/servidor/estado`.

## eventId

Cada evento lleva un `eventId` único, incluso si el ESP32 se reinicia:

```
{deviceId}-{random de arranque en hex}-{contador}
equipo-01-7f3a-0042
```

El random se genera una vez en cada arranque y el contador sube con cada evento **nuevo**. Un reintento reutiliza el mismo `eventId`.

## Respuestas

El servidor responde **cada** evento en `resp`:

- Aceptado: `{"eventId":"...","ok":true, ...datos}`
- Rechazado: `{"eventId":"...","ok":false,"motivo":"CODIGO_INVALIDO"}`

| motivo | Cuándo |
| --- | --- |
| `CODIGO_INVALIDO` | El código no corresponde a ninguna reserva pendiente |
| `CODIGO_VENCIDO` | La reserva existe pero ya venció |
| `LLAVE_DESCONOCIDA` | El UID no está cargado en el sistema |
| `SIN_PRESTAMO_ACTIVO` | El UID existe pero esa llave no estaba prestada |
| `DATOS_INVALIDOS` | El JSON no respeta el formato del evento (ej. código con letras, UID que no es hex, tipo de evento desconocido) |
| `ERROR_INTERNO` | Falla del servidor. El ESP32 muestra un error y no entrega nada |

## Eventos (ESP32 → servidor)

### `inicio`
Se publica al arrancar y en cada reconexión. Informa la configuración del disco.

```json
→ evt/inicio  {"eventId":"equipo-01-7f3a-0001","slotsTotales":32,"slotsReservados":[0]}
← resp        {"eventId":"equipo-01-7f3a-0001","ok":true,"slotReposo":5}
```
`slotsReservados`: slots que nunca llevan llave (ej. el del tag HOME). `slotReposo`: el slot vacío más cercano al 0 (donde queda el disco después del homing), contando que el disco es circular.

### `solicitud_retiro`
El docente ingresó un código en el teclado.

```json
→ evt/solicitud_retiro  {"eventId":"equipo-01-7f3a-0042","codigo":"482913"}
← resp  {"eventId":"equipo-01-7f3a-0042","ok":true,"slot":7,"uid":"04A1B2C3","aula":"214","apellido":"Perez"}
← resp  {"eventId":"equipo-01-7f3a-0042","ok":false,"motivo":"CODIGO_VENCIDO"}
```
Si acepta el código, el servidor extiende la reserva al menos `RETIRO_MARGEN_SEGUNDOS` (120 s), para que no venza mientras el disco gira y el docente retira la llave.

### `retiro_confirmado`
El UID esperado dejó de leerse de forma estable: el docente se llevó la llave. `slot` es donde estaba **realmente** (puede diferir del informado si hubo que buscarla).

```json
→ evt/retiro_confirmado  {"eventId":"equipo-01-7f3a-0043","codigo":"482913","uid":"04A1B2C3","slot":8}
← resp  {"eventId":"equipo-01-7f3a-0043","ok":true}
```
El servidor marca la reserva `USADA` y la llave `PRESTADA`, y crea el `Prestamo`. El slot que quedó vacío pasa a ser la posición de reposo.

### `retiro_timeout`
Nadie retiró la llave en 60 s. El disco vuelve a dejar un slot vacío en la ventana. La reserva sigue vigente hasta que vence.

```json
→ evt/retiro_timeout  {"eventId":"equipo-01-7f3a-0044","codigo":"482913"}
← resp  {"eventId":"equipo-01-7f3a-0044","ok":true}
```

### `devolucion`
Se leyó un UID estable en el slot de la ventana después de apretar `B`.

```json
→ evt/devolucion  {"eventId":"equipo-01-7f3a-0050","uid":"04A1B2C3","slot":5}
← resp  {"eventId":"equipo-01-7f3a-0050","ok":true,"aula":"214","apellido":"Perez","slotReposo":12}
← resp  {"eventId":"equipo-01-7f3a-0050","ok":false,"motivo":"SIN_PRESTAMO_ACTIVO"}
```
Si se acepta, el servidor cierra el préstamo activo de esa llave, la pasa a `DISPONIBLE` y actualiza su `slot`. El disco gira a `slotReposo`: el slot vacío más cercano al de la devolución. Es `null` si el disco está lleno.

### `error`
Falla del equipo que el servidor registra como **incidente**: el preceptor la ve en la web (US-05).

| Campo | Obligatorio | Qué es |
| --- | --- | --- |
| `error` | sí | `LLAVE_NO_ENCONTRADA` o `MOTOR_NO_GIRA` (el homing no encontró el tag HOME). Otro valor se muestra tal cual |
| `codigo` | no | El de la reserva que se estaba entregando: así el servidor sabe el aula y el docente |
| `detalle` | no | Texto libre, hasta 200 caracteres |

```json
→ evt/error  {"eventId":"equipo-01-7f3a-0045","error":"LLAVE_NO_ENCONTRADA","codigo":"482913","detalle":"uid 04A1B2C3, slot 7"}
← resp  {"eventId":"equipo-01-7f3a-0045","ok":true}
```

Cuándo se manda `LLAVE_NO_ENCONTRADA` (US-05, "falla 2 veces seguidas"): en el **intento 1** el disco va al slot y prueba los vecinos (±1); en el **intento 2** repite el homing y la vuelve a buscar. Si tampoco aparece, el LCD muestra "Pedi la llave" / "en porteria", el disco vuelve a un slot vacío y se manda el `error`. La reserva no se cancela: vence sola.

## Comandos (servidor → ESP32)

| Comando | Payload |
| --- | --- |
| `recalibrar` | `{"comando":"recalibrar"}`: repite el homing y la medición de pasos por vuelta |

## Reintentos y duplicados

- Si el ESP32 no recibe una respuesta en 5 s, muestra "Sin respuesta" en el LCD y **reenvía el mismo evento con el mismo `eventId`**.
- El servidor guarda cada evento en `EventoDispositivo` (`eventId` único). Si llega un `eventId` repetido, **no lo vuelve a procesar**, pero reenvía la respuesta que ya había dado (también si fue un rechazo). Si no la reenviara, el ESP32 quedaría reintentando para siempre en los casos en que se perdió la respuesta y no el evento.
- Excepción: un `ERROR_INTERNO` no se guarda, así el reintento se procesa de nuevo.
- El evento y sus cambios se guardan en la misma transacción: o queda todo registrado o nada.
- Sin conexión, el equipo no entrega ni recibe llaves (LCD "Sin conexion").

## Seguridad del broker

- Desarrollo: Mosquitto anónimo, solo en `localhost`.
- Demo: un usuario y contraseña por equipo, y una ACL que limite cada equipo a `llavetrack/v1/{su deviceId}/#`.
