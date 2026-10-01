import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import config
from app.db import SesionLocal
from app.errores import registrar_manejadores
from app.mqtt_cliente import ClienteMqtt
from app.rutas import aulas, reservas

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    """Al arrancar el servidor se conecta a MQTT; al apagarlo se desconecta."""
    cliente_mqtt = None
    if config.mqtt_habilitado:
        cliente_mqtt = ClienteMqtt(SesionLocal)
        cliente_mqtt.iniciar()
    yield
    if cliente_mqtt:
        cliente_mqtt.detener()


app = FastAPI(title="LlaveTrack API", lifespan=ciclo_de_vida)
registrar_manejadores(app)
app.include_router(aulas.router)
app.include_router(reservas.router)


@app.get("/api/salud")
def salud():
    """La usa la web para saber si el servidor esta levantado."""
    return {"ok": True}
