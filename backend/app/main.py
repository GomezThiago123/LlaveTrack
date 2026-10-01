from fastapi import FastAPI

app = FastAPI(title="LlaveTrack API")


@app.get("/api/salud")
def salud():
    """La usa la web para saber si el servidor esta levantado."""
    return {"ok": True}
