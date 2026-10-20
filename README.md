# LlaveTrack

Sistema para retirar y devolver las llaves de las aulas de la ETEC-UBA. El docente reserva la llave desde la web, ingresa un código en el equipo y un disco giratorio le entrega su llave. Cada llave tiene un tag RFID, así el sistema registra quién la retiró, quién la devolvió y a qué hora.

## Estructura

| Carpeta | Qué hay |
| --- | --- |
| `backend/` | API REST + MQTT en Python (FastAPI). Incluye `simulador/`, que se hace pasar por el equipo para probar sin hardware |
| `frontend/` | Aplicación web mobile-first (React + Vite + TypeScript) |
| `docs/` | Protocolo MQTT y documentación |

El backend y el frontend son independientes: cada uno se instala y se levanta **en su propia terminal**.

## Backend

Requisito: **Python 3.11 o más nuevo** (`python3 --version`, en Windows `py --version`).
- Windows: instalador de [python.org](https://www.python.org/downloads/) marcando "Add python.exe to PATH".
- Linux Mint: viene instalado. Si falta el módulo de entornos virtuales: `sudo apt install python3-venv`.

### Primera vez

Linux:
```sh
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):
```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
Si PowerShell no deja activar el entorno, corré una sola vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Después, con el entorno activado, creá la base de datos y cargá los datos iniciales (las 30 aulas con su llave y los usuarios de prueba de `seed/datos.json`):
```sh
alembic upgrade head
python -m app.seed
```

El archivo `.env` es opcional: sin él se usan los valores por defecto. Para cambiarlos, copiá `.env.example` a `.env`.

**Base en Supabase (opcional):** por defecto la base es un archivo SQLite local. Para usar la de Supabase, en el dashboard tocá **Connect** → **Session pooler**, copiá la URL y ponela en `backend/.env` como `DATABASE_URL`, cambiando `postgresql://` por `postgresql+psycopg://` (ejemplo en `.env.example`). Después corré `alembic upgrade head` y `python -m app.seed` como arriba. Ojo: es una sola base para todo el grupo, así que cualquier `--reiniciar` o migración afecta a todos.

### Cada vez

Activá el entorno virtual (`source .venv/bin/activate` en Linux, `.venv\Scripts\Activate.ps1` en Windows). Vas a ver `(.venv)` al principio de la línea. Después:

| Comando | Qué hace |
| --- | --- |
| `python run.py` | Levanta el servidor en `http://localhost:8000`. Se reinicia solo cuando cambiás el código |
| `pytest` | Corre los tests (usan una base temporal con `tests/datos_prueba.json` e ignoran tu `.env`: nunca tocan `llavetrack.db` ni Supabase) |
| `alembic upgrade head` | Aplica las migraciones pendientes a la base (correrlo después de cada `git pull`) |
| `python -m app.seed --reiniciar` | **Borra todos los datos** y vuelve a cargar `seed/datos.json` |
| `python simulador/simulador.py` | Simulador del equipo (ver abajo) |

Con el servidor levantado, en `http://localhost:8000/docs` está la documentación interactiva de la API, que genera FastAPI. Para probar las rutas que piden login, primero ejecutá `POST /api/auth/login` ahí mismo: el navegador guarda la cookie de sesión y la manda en los pedidos siguientes.

### Usuarios de prueba

Los de `seed/datos.json`, todos con la contraseña `llavetrack`:

| Email | Rol |
| --- | --- |
| `ana.perez@example.com` | Docente |
| `bruno.gomez@example.com` | Docente |
| `carla.diaz@example.com` | Preceptora |
| `admin@example.com` | Administrador |

5 contraseñas incorrectas seguidas bloquean la cuenta 15 minutos. Para "Olvidé mi contraseña": si no configuraste un servidor de mail (`SMTP_*` en `.env`), el link de recuperación aparece en la terminal del servidor.

### MQTT y simulador del equipo

El servidor se conecta al broker **Mosquitto** en `localhost:1883` (Linux: `sudo apt install mosquitto mosquitto-clients`; Windows: instalador de [mosquitto.org](https://mosquitto.org/download/)). Si el broker no está, la API funciona igual y el servidor reintenta conectarse solo.

El simulador se hace pasar por el equipo (ESP32), así se puede probar todo sin hardware. Como el equipo real, **queda prendido** hasta que lo apagues: al arrancar se conecta, avisa que está en línea y después manda un "latido" cada 30 s. En otra terminal, desde `backend/` con el entorno activado:

```sh
python simulador/simulador.py
```

Los comandos se escriben en el prompt `equipo>`:

| Comando | Qué simula |
| --- | --- |
| `retirar 482913` | Ingresa el código de una reserva y retira la llave |
| `timeout 482913` | Ingresa el código pero nadie retira la llave |
| `devolver 04A00214` | Cuelga la llave con ese UID en el lugar vacío de la ventana |
| `desenchufar` | Corte de luz: deja de responder sin avisar. A los ~15 s el servidor lo ve desconectado |
| `enchufar` | Vuelve a arrancar después de `desenchufar` |
| `pantalla` | Muestra los dos LEDs (conexión y faltantes) y cómo rota el LCD en reposo |
| `salir` | Se apaga prolijo (también con Ctrl+C) y queda desconectado enseguida |

Muestra cada mensaje MQTT (`→` lo que manda el equipo, `←` lo que responde el servidor) y lo que mostraría el LCD. Con `--repetir` manda cada evento dos veces, para ver que el servidor no lo procesa dos veces. Los UID de las llaves están en `seed/datos.json`: por ahora son inventados, `04A0` + el número de aula (la del 214 es `04A00214`).

Mientras el equipo está desconectado, la web no deja pedir llaves (US-20). El simulador también muestra los LEDs: el de faltantes se prende cuando hay llaves prestadas (US-21) y el de conexión titila si se cae el broker o el servidor; en ese caso no deja retirar ni devolver (US-22).

Para ver todos los mensajes del broker: `mosquitto_sub -v -t 'llavetrack/#'` o MQTTX.

## Frontend

Requisito: **Node.js 20.19 o más nuevo** (recomendado: 24 LTS). Verificalo con `node --version`.
- Windows: instalador de [nodejs.org](https://nodejs.org) o `winget install OpenJS.NodeJS.LTS`.
- Linux: con [nvm](https://github.com/nvm-sh/nvm), corré `nvm install` dentro de `frontend/` (lee la versión de `.nvmrc`).

```sh
cd frontend
npm install        # solo la primera vez, o cuando cambie package.json
npm run dev
```

La web queda en `http://localhost:5173` y se actualiza sola cuando cambiás el código. Todo lo que empieza con `/api` lo reenvía al backend (puerto 8000), así que **el backend tiene que estar levantado en otra terminal**.

Para abrir la web **desde el celular**, conectalo a la misma red WiFi y entrá a `http://<IP-de-la-compu>:5173`. Vite muestra la IP en la terminal, en la línea `Network`. Si vas a probar "Olvidé mi contraseña" desde el celular, poné esa misma dirección en `WEB_URL` del `backend/.env`, así el link del mail apunta a la compu.

| Pantalla | Qué hay |
| --- | --- |
| `/` | Sin login: estado de cada aula y si el equipo está en línea |
| `/login`, `/recuperar`, `/restablecer` | Ingresar y recuperar la contraseña |
| `/aulas` | Con login: pedir una llave. Preceptores y admin ven quién tiene cada una y su teléfono |
| `/codigo` | El código para el equipo, con cuenta regresiva. Avisa cuando se retiró la llave |

Las pantallas de aulas y del código se actualizan solas cada 5 segundos.

| Comando | Qué hace |
| --- | --- |
| `npm run dev` | Levanta la web en modo desarrollo |
| `npm run build` | Compila la web para producción (queda en `dist/`) |
