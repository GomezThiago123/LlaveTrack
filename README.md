# LlaveTrack

Sistema para retirar y devolver las llaves de las aulas de la ETEC-UBA. El docente reserva la llave desde la web, ingresa un código en el equipo y un disco giratorio le entrega su llave. Cada llave tiene un tag RFID, así el sistema registra quién la retiró, quién la devolvió y a qué hora.

## Estructura

| Carpeta | Qué hay |
| --- | --- |
| `server/` | API REST + MQTT (Python + FastAPI) |
| `web/` | Aplicación web mobile-first (React + Vite + TypeScript) |
| `tools/simulador/` | CLI en Python que se hace pasar por el equipo, para probar sin hardware |
| `docs/` | Protocolo MQTT y documentación |
| `scripts/` | Scripts de Node que hacen que los comandos funcionen igual en Windows y en Linux |

Python usa un entorno virtual (`.venv`, en la raíz) con las dependencias de `requirements.txt`. La web usa npm. Los comandos de abajo se encargan de los dos.

## Requisitos

- **Python 3.10 o más nuevo.** Verificalo con `python3 --version` (en Windows: `py --version`).
  - Windows: instalador de [python.org](https://www.python.org/downloads/) o `winget install Python.Python.3.12`.
  - Linux Mint: viene instalado. Si falta el módulo de entornos virtuales: `sudo apt install python3-venv`.
- **Node.js 22.12 o más nuevo** (recomendado: 24 LTS), para la web. Verificalo con `node --version`.
  - Windows: instalador de [nodejs.org](https://nodejs.org) o `winget install OpenJS.NodeJS.LTS`.
  - Linux: con [nvm](https://github.com/nvm-sh/nvm), corré `nvm install` desde la raíz del repo (lee la versión de `.nvmrc`).
- Git.

## Primera vez

```sh
npm run setup
```

Crea el entorno virtual de Python, instala las dependencias de Python y de Node, y copia `server/.env.example` a `server/.env`. Con los valores por defecto alcanza para desarrollar. Si cambia `requirements.txt` o `package.json`, volvé a correrlo.

## Levantar todo en desarrollo

```sh
npm run dev
```

Levanta el servidor en `http://localhost:8000` y la web en `http://localhost:5173`. Los dos se reinician solos cuando cambiás el código.

- Documentación interactiva de la API (la genera FastAPI): `http://localhost:8000/docs`.
- Para abrir la web **desde el celular**, conectalo a la misma red WiFi y entrá a `http://<IP-de-la-compu>:5173`. Vite muestra la IP en la terminal, en la línea `Network`.

## Otros comandos

| Comando | Qué hace |
| --- | --- |
| `npm test` | Corre los tests del servidor (pytest) |
| `npm run build` | Compila la web para producción |
| `npm run simulador -- <comando>` | Corre el simulador del equipo (llega en la Fase 1) |
