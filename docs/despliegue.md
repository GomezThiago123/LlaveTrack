# Subir LlaveTrack a la nube (gratis)

Guía para dejar la web, el servidor y el equipo funcionando en internet, sin pagar nada y sin comprar un dominio. **Si algún servicio pide tarjeta, frená:** no hace falta, y sin tarjeta no te pueden cobrar.

```
Celular ──HTTPS──► Render (web + servidor) ──► Supabase (base)
                          │
                          │ MQTT con TLS (8883)
                          ▼
                     HiveMQ Cloud ◄──MQTT con TLS (8883)── Equipo (ESP32)

cron-job.org ──cada 10 min──► Render (para que no se duerma)
```

| Pieza | Servicio | Límite del plan gratis |
| --- | --- | --- |
| Web y servidor, con HTTPS | Render | Se duerme tras 15 min sin tráfico y tarda ~1 min en volver. 750 horas por mes: alcanza para un servicio prendido todo el mes |
| Broker MQTT | HiveMQ Cloud | Unas 100 conexiones |
| Mail | Brevo | Unos 300 mails por día |
| Base | Supabase (ya está) | Se pausa tras 7 días sin actividad |
| Ping | cron-job.org | — |

La dirección queda como `https://llavetrack.onrender.com`: no es un dominio propio, pero tiene HTTPS y es gratis.

Los secretos van **solo** en el panel de Render, en `backend/.env` y en `firmware/include/secrets.h`. Nunca en el repo: es público.

## 1. Cambiar las contraseñas de prueba (primero de todo)

La contraseña `llavetrack` figura en el repo público. Con la web en internet, cualquiera podría entrar como preceptor. Por eso se cambia **antes** de subirla.

1. En Supabase: botón **Connect** → **Session pooler**. Copiá la URL y cambiá `postgresql://` por `postgresql+psycopg://`.
2. Ponela en `backend/.env` como `DATABASE_URL` (ejemplo en `backend/.env.example`). Guardala aparte: se usa otra vez en el paso 4.
3. Con el entorno activado, desde `backend/`:

```sh
alembic upgrade head
python -m app.cambiar_clave ana.perez@example.com
python -m app.cambiar_clave bruno.gomez@example.com
python -m app.cambiar_clave carla.diaz@example.com
python -m app.cambiar_clave admin@example.com
```

Cada comando muestra a qué base va a escribir: tiene que decir `pooler.supabase.com`. Si dice `sqlite`, el `.env` no se está leyendo.

Cuando termines, volvé a comentar `DATABASE_URL` en `backend/.env` para seguir desarrollando con SQLite y no pisar la base de la demo.

## 2. HiveMQ Cloud (el broker)

1. Creá una cuenta en [hivemq.com](https://www.hivemq.com/) y un cluster del plan gratis.
2. Anotá la dirección del cluster (algo como `xxxx.s1.eu.hivemq.cloud`) y confirmá que el puerto TLS sea el **8883**.
3. En **Access Management** creá dos credenciales, con claves distintas y largas:
   - `servidor`, para Render;
   - `equipo-01`, para la placa y el simulador.
4. Si el plan permite limitar por tópico, dales estos permisos:
   - `servidor`: `llavetrack/v1/#`;
   - `equipo-01`: `llavetrack/v1/equipo-01/#` y solo lectura en `llavetrack/v1/servidor/estado`.

   Si no lo permite, anotalo en `PENDIENTES.md`: con un solo equipo el riesgo es bajo.

## 3. Brevo (el mail)

1. Creá una cuenta en [brevo.com](https://www.brevo.com/).
2. En **Senders** agregá y verificá el mail que va a mandar los avisos. Puede ser un Gmail.
3. En **SMTP & API** → **API Keys**, creá una clave y copiala.

Al no tener dominio propio, los mails pueden caer en spam. Para la demo, avisá que revisen esa carpeta.

## 4. Render (la web y el servidor)

Render construye lo que está en GitHub: **antes hay que subir los cambios con `git push`**.

1. Creá una cuenta en [render.com](https://render.com/) y conectala con GitHub.
2. **New** → **Blueprint** → elegí el repo `LlaveTrack`. Render lee `render.yaml`.
3. Completá los valores que pide:

| Variable | Valor |
| --- | --- |
| `DATABASE_URL` | La de Supabase, con `postgresql+psycopg://` (paso 1) |
| `WEB_URL` | `https://llavetrack.onrender.com` |
| `MQTT_HOST` | La dirección del cluster, sin `https://` ni puerto |
| `MQTT_USUARIO` | `servidor` |
| `MQTT_CLAVE` | La de `servidor` |
| `BREVO_API_KEY` | La clave de Brevo |
| `BREVO_REMITENTE` | El mail verificado en Brevo |

4. Esperá que termine la primera construcción (unos minutos). Si el nombre `llavetrack` estaba ocupado, Render te da otra dirección: corregí `WEB_URL` con esa.

**Cómo saber que anduvo:**
- `https://TU-DIRECCION/api/salud` responde `{"ok":true}`.
- En los logs de Render aparece `Conectado al broker MQTT`.
- La web abre, y podés entrar con la contraseña nueva.

La web va a decir "Equipo desconectado" hasta el paso 6.

## 5. El ping (para que no se duerma)

1. Creá una cuenta en [cron-job.org](https://cron-job.org/).
2. Creá un trabajo que pida `https://TU-DIRECCION/api/publico/estado` **cada 10 minutos**.

Se usa esa dirección y no `/api/salud` porque también consulta la base: un solo ping mantiene despiertos a Render y a Supabase.

Después de unas horas, revisá el historial del trabajo: todas las respuestas tienen que ser 200 y tardar poco. Una que tarde cerca de un minuto significa que el servicio se durmió.

## 6. Probar con el simulador, sin la placa

Con la placa **apagada** (los dos se presentan como `equipo-01`), desde `backend/` con el entorno activado:

```sh
python simulador/simulador.py --host xxxx.s1.eu.hivemq.cloud --tls --usuario equipo-01
```

Pide la clave de `equipo-01`. En la web, en menos de 5 s, tiene que aparecer **Equipo en línea**. Después:

1. Como docente, pedí una llave y anotá el código.
2. En el simulador: `retirar CODIGO`. El aula pasa a Ocupada.
3. En el simulador: `devolver UID` (los UID están en `backend/seed/datos.json`). El aula vuelve a Disponible.
4. Como preceptor, en **Docentes**, dá de alta a alguien con un mail real. Tiene que llegarle el link para crear su contraseña.

Salí con `salir` antes de prender la placa.

## 7. La placa

Primero, comprobá que la WiFi deje salir por el 8883: desde una compu en esa red, conectate con MQTTX al cluster (SSL activado). Si no conecta, usá el hotspot de un celular.

En `firmware/include/secrets.h`:

```cpp
constexpr const char *MQTT_HOST = "xxxx.s1.eu.hivemq.cloud";
constexpr int MQTT_PUERTO = 8883;
constexpr const char *MQTT_USUARIO = "equipo-01";
constexpr const char *MQTT_CLAVE = "la-clave-de-equipo-01";
constexpr bool MQTT_TLS = true;
constexpr const char *MQTT_CA_PEM = "";
```

Cargá el firmware con PlatformIO y mirá el Monitor Serie. Con `MQTT_CA_PEM` vacío, el aviso `OJO: TLS sin certificado de la CA` es esperable: la conexión va cifrada, pero sin verificar con quién habla. Sirve para la primera prueba.

**Cuando conecte, agregá el certificado.** Para ver quién firmó el del broker:

```sh
openssl s_client -connect xxxx.s1.eu.hivemq.cloud:8883 -servername xxxx.s1.eu.hivemq.cloud -showcerts </dev/null | grep -E '^ *[0-9]+ s:|i:'
```

Bajá el certificado raíz de esa autoridad, en formato PEM, y pegalo así en `secrets.h`:

```cpp
constexpr const char *MQTT_CA_PEM = R"(-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
)";
```

Tiene que seguir conectando. El certificado raíz vence, pero recién dentro de años: para la demo no hay que renovarlo.

Con todo andando, medí un retiro y una devolución con el equipo real y anotá los tiempos en `PENDIENTES.md`.

## Si algo falla

| Qué pasa | Qué mirar |
| --- | --- |
| La web tarda ~1 min en abrir | Render estaba dormido: revisá el ping |
| Logs de Render: `No se pudo conectar al broker` | `MQTT_HOST`, `MQTT_USUARIO`, `MQTT_CLAVE` y que `MQTT_TLS` sea `true` |
| Logs de Render: error de base al arrancar | `DATABASE_URL`: tiene que tener `postgresql+psycopg://` y el Session pooler (puerto 5432) |
| Monitor Serie: `estado -2` | La WiFi no deja salir por el 8883, o la dirección está mal |
| Monitor Serie: `estado 4` o `5` | Usuario o clave de `equipo-01` |
| LCD: `Sin conexion / Servidor` | Render está dormido o caído. Abrí la web, esperá un minuto y mirá los logs |
| No llegan los mails | Spam, y en Brevo la sección de logs de mails. El remitente tiene que estar verificado |
| El link del mail apunta a otra dirección | `WEB_URL` en Render |
| No se puede entrar: "Tu sesión venció" enseguida | `WEB_URL` y que estés entrando por `https://` (la cookie solo viaja por HTTPS) |
| Supabase pausado | Se reactiva a mano desde su panel. Revisá que el ping siga andando |

## Plan B para la demo

Si la red de la escuela o algún servicio falla el día de la demo, todo corre en una compu con el hotspot de un celular: Mosquitto, `python run.py` y `npm run dev`, con la placa apuntando a la IP de la compu (ver README). No depende de internet salvo por la base, si sigue en Supabase. Con `DATABASE_URL` comentada usa SQLite local, y hay que cargar el seed con `python -m app.seed`. **Probalo antes de la demo.**
