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
| `python simulador/simulador.py` | Corre el simulador del equipo (llega en la Fase 1) |

Con el servidor levantado, en `http://localhost:8000/docs` está la documentación interactiva de la API, que genera FastAPI.

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

Para abrir la web **desde el celular**, conectalo a la misma red WiFi y entrá a `http://<IP-de-la-compu>:5173`. Vite muestra la IP en la terminal, en la línea `Network`.

| Comando | Qué hace |
| --- | --- |
| `npm run dev` | Levanta la web en modo desarrollo |
| `npm run build` | Compila la web para producción (queda en `dist/`) |
