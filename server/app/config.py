from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Configuracion del servidor. Lee server/.env y las variables de entorno.

    Los tiempos y limites del sistema se van a agregar aca, con sus valores por defecto.
    """

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        extra="ignore",
    )

    port: int = 8000


config = Config()
