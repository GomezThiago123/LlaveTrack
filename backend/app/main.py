import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.config import config
from app.db import SesionLocal
from app.errores import registrar_manejadores
from app.mqtt_cliente import ClienteMqtt
from app.tareas import TareaRecordatorios
from app.rutas import aulas, auth, equipo, incidentes, prestamos, reservas, usuarios

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(aplicacion: FastAPI):
    """Al arrancar el servidor se conecta a MQTT y arranca los avisos de US-16; al apagarlo, los frena."""
    cliente_mqtt = None
    if config.mqtt_habilitado:
        cliente_mqtt = ClienteMqtt(SesionLocal)
        cliente_mqtt.iniciar()
    # Las rutas que mandan comandos al equipo (ej. recalibrar) lo buscan aca
    aplicacion.state.cliente_mqtt = cliente_mqtt
    tarea = None
    if config.recordatorios_habilitados:  # US-16: avisos automaticos por mail
        tarea = TareaRecordatorios()
        tarea.start()
    yield
    if tarea:
        tarea.detener()
    if cliente_mqtt:
        cliente_mqtt.detener()


app = FastAPI(title="LlavesUBA API", lifespan=ciclo_de_vida)
registrar_manejadores(app)
app.include_router(auth.router)
app.include_router(aulas.router)
app.include_router(reservas.router)
app.include_router(usuarios.router)
app.include_router(incidentes.router)
app.include_router(prestamos.router)
app.include_router(equipo.router)


@app.get("/api/salud")
def salud():
    """La usa la web para saber si el servidor esta levantado."""
    return {"ok": True}


def montar_web(aplicacion: FastAPI, carpeta: str | Path) -> None:
    """Entrega la web compilada (npm run build) desde este servidor, en la nube.

    Un archivo que existe (ej. /assets/index-abc.js) se entrega tal cual; cualquier otra
    direccion (ej. /aulas) devuelve index.html y la resuelve React. Lo que empieza con /api
    nunca llega aca si existe; si no existe, es un 404 de la API.
    """
    raiz = Path(carpeta).resolve()

    @aplicacion.get("/{ruta:path}", include_in_schema=False)
    def web(ruta: str):
        if ruta == "api" or ruta.startswith("api/"):
            raise HTTPException(status_code=404)
        archivo = (raiz / ruta).resolve()
        # is_relative_to: que nadie pida ../../ y se lleve un archivo de fuera de la carpeta
        if ruta and archivo.is_relative_to(raiz) and archivo.is_file():
            return FileResponse(archivo)
        return FileResponse(raiz / "index.html")


if config.web_dist:
    montar_web(app, config.web_dist)
