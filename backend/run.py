# Levanta el servidor en modo desarrollo: se reinicia solo cuando cambia el codigo.
from pathlib import Path

import uvicorn

from app.config import config

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        # Solo localhost: el celular entra por el proxy de Vite (puerto 5173)
        host="127.0.0.1",
        port=config.port,
        reload=True,
        reload_dirs=[str(Path(__file__).parent / "app")],
    )
