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

Después, con el entorno activado, creá la base de datos y cargá los datos de prueba (aulas, llaves y usuarios de `seed/datos.json`):
```sh
alembic upgrade head
python -m app.seed
```

El archivo `.env` es opcional: sin él se usan los valores por defecto. Para cambiarlos, copiá `.env.example` a `.env`.

### Cada vez

Activá el entorno virtual (`source .venv/bin/activate` en Linux, `.venv\Scripts\Activate.ps1` en Windows). Vas a ver `(.venv)` al principio de la línea. Después:

| Comando | Qué hace |
| --- | --- |
| `python run.py` | Levanta el servidor en `http://localhost:8000`. Se reinicia solo cuando cambiás el código |
| `pytest` | Corre los tests (usan una base temporal, no tocan `llavetrack.db`) |
| `alembic upgrade head` | Aplica las migraciones pendientes a la base (correrlo después de cada `git pull`) |
| `python -m app.seed --reiniciar` | **Borra todos los datos** y vuelve a cargar `seed/datos.json` |
| `python simulador/simulador.py --help` | Simulador del equipo (ver abajo) |

Con el servidor levantado, en `http://localhost:8000/docs` está la documentación interactiva de la API, que genera FastAPI. Para probar las rutas que piden login, primero ejecutá `POST /api/auth/login` ahí mismo: el navegador guarda la cookie de sesión y la manda en los pedidos siguientes.

### Usuarios de prueba

Los de `seed/datos.json`, todos con la contraseña `llavetrack`:

| Email | Rol |
| --- | --- |
| `ana.perez@example.com` | Docente |
| `bruno.gomez@example.com` | Docente |
| `carla.diaz@example.com` | Preceptora (ve quién tiene cada llave) |
| `admin@example.com` | Administrador |

5 contraseñas incorrectas seguidas bloquean la cuenta 15 minutos. Para "Olvidé mi contraseña": si no configuraste un servidor de mail (`SMTP_*` en `.env`), el link de recuperación aparece en la terminal del servidor.

### MQTT y simulador del equipo

El servidor se conecta al broker **Mosquitto** en `localhost:1883` (Linux: `sudo apt install mosquitto mosquitto-clients`; Windows: instalador de [mosquitto.org](https://mosquitto.org/download/)). Si el broker no está, la API funciona igual y el servidor reintenta conectarse solo.

El simulador se hace pasar por el equipo (ESP32), así se puede probar todo sin hardware. En otra terminal, desde `backend/` con el entorno activado:

```sh
python simulador/simulador.py inicio              # el equipo arranca y queda online
python simulador/simulador.py retirar 482913      # ingresa el código de una reserva y retira la llave
python simulador/simulador.py devolver 04A1B2C3   # cuelga la llave con ese UID
python simulador/simulador.py timeout 482913      # ingresa el código pero nadie retira la llave
python simulador/simulador.py offline             # el equipo se desconecta
```

Muestra cada mensaje MQTT (`→` lo que manda el equipo, `←` lo que responde el servidor) y lo que mostraría el LCD. Con `--repetir` manda cada evento dos veces, para ver que el servidor no lo procesa dos veces. Los UID de las llaves están en `seed/datos.json`.

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
