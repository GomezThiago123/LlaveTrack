from fastapi import FastAPI

from app.errores import registrar_manejadores
from app.rutas import reservas

app = FastAPI(title="LlaveTrack API")
registrar_manejadores(app)
app.include_router(reservas.router)


@app.get("/api/salud")
def salud():
    """La usa la web para saber si el servidor esta levantado."""
    return {"ok": True}
