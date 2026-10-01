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
| `resp` | servidor | no | Respuesta a cada evento, con el mismo `eventId` |
| `cmd` | servidor | no | Comandos al equipo |

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
→ evt/inicio  {"eventId":"equipo-01-7f3a-0001","slotsTotales":24,"slotsReservados":[0]}
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
Falla del equipo que el servidor tiene que registrar (ej. no encontró la llave pedida).

```json
→ evt/error  {"eventId":"equipo-01-7f3a-0045","error":"LLAVE_NO_ENCONTRADA","detalle":"uid 04A1B2C3, slot 7"}
← resp  {"eventId":"equipo-01-7f3a-0045","ok":true}
```

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
