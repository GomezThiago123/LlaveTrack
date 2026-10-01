from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

CARPETA_BACKEND = Path(__file__).parent.parent


class Config(BaseSettings):
    """Configuracion del servidor. Lee backend/.env y las variables de entorno.

    Cada campo se puede cambiar en el .env con su nombre en mayusculas (ej. RESERVA_MINUTOS=5).
    """

    model_config = SettingsConfigDict(env_file=CARPETA_BACKEND / ".env", extra="ignore")

    port: int = 8000

    # Base de datos. Por defecto, un archivo SQLite en backend/llavetrack.db
    database_url: str = f"sqlite:///{CARPETA_BACKEND / 'llavetrack.db'}"

    # Minutos que tiene el docente para ir al equipo con su codigo
    reserva_minutos: int = 10

    # TEMPORAL hasta el login (Fase 2): permite indicar el usuario con el
    # encabezado X-Usuario-Email. Nunca activarlo en la demo.
    modo_desarrollo: bool = True


config = Config()
