# LlaveTrack

Sistema para retirar y devolver las llaves de las aulas de la ETEC-UBA. El docente reserva la llave desde la web, ingresa un código en el equipo y un disco giratorio le entrega su llave. Cada llave tiene un tag RFID, así el sistema registra quién la retiró, quién la devolvió y a qué hora.

## Estructura

| Carpeta | Qué hay |
| --- | --- |
| `server/` | API REST + MQTT (Node + TypeScript + Express) |
| `web/` | Aplicación web mobile-first (React + Vite + TypeScript) |
| `tools/simulador/` | CLI que se hace pasar por el equipo, para probar sin hardware |
| `docs/` | Protocolo MQTT y documentación |

Las tres carpetas de código son *workspaces* de npm: se instalan juntas con un solo `npm install` desde la raíz.

## Requisitos

- **Node.js 22.12 o más nuevo** (recomendado: 24 LTS). Verificalo con `node --version`.
  - Windows: instalador de [nodejs.org](https://nodejs.org) o `winget install OpenJS.NodeJS.LTS`.
  - Linux: [nvm](https://github.com/nvm-sh/nvm) y después `nvm install` desde la raíz del repo (lee la versión de `.nvmrc`).
- Git.

## Primera vez

```sh
npm install
```

Después copiá `server/.env.example` a `server/.env`. Con los valores por defecto alcanza para desarrollar.

- Linux: `cp server/.env.example server/.env`
- Windows (PowerShell): `Copy-Item server/.env.example server/.env`

## Levantar todo en desarrollo

```sh
npm run dev
```

Levanta el servidor en `http://localhost:3000` y la web en `http://localhost:5173`. Los dos se reinician solos cuando cambiás el código.

Para abrir la web **desde el celular**, conectalo a la misma red WiFi y entrá a `http://<IP-de-la-compu>:5173`. Vite muestra la IP en la terminal, en la línea `Network`.

## Otros comandos

| Comando | Qué hace |
| --- | --- |
| `npm test` | Corre los tests del servidor |
| `npm run build` | Compila el servidor y la web |
| `npm run simulador -- <comando>` | Corre el simulador del equipo (llega en la Fase 1) |
