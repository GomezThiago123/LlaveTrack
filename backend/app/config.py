import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

CARPETA_BACKEND = Path(__file__).parent.parent

# Los tests ponen LLAVETRACK_TESTS=1 (conftest.py) para no leer el .env de cada uno:
# asi siempre usan los valores por defecto y nunca la base de Supabase.
ARCHIVO_ENV = None if os.environ.get("LLAVETRACK_TESTS") else CARPETA_BACKEND / ".env"


class Config(BaseSettings):
    """Configuracion del servidor. Lee backend/.env y las variables de entorno.

    Cada campo se puede cambiar en el .env con su nombre en mayusculas (ej. RESERVA_MINUTOS=5).
    """

    model_config = SettingsConfigDict(env_file=ARCHIVO_ENV, extra="ignore")

    port: int = 8000

    # Base de datos. Por defecto, un archivo SQLite en backend/llavetrack.db
    database_url: str = f"sqlite:///{CARPETA_BACKEND / 'llavetrack.db'}"

    # Minutos que tiene el docente para ir al equipo con su codigo (US-03: 2 min)
    reserva_minutos: int = 2

    # Cuando el equipo acepta un codigo, la reserva se extiende al menos estos segundos,
    # para que no venza mientras el disco gira y el docente retira la llave
    retiro_margen_segundos: int = 120

    # Broker MQTT (Mosquitto)
    mqtt_habilitado: bool = True
    mqtt_host: str = "localhost"
    mqtt_puerto: int = 1883
    mqtt_usuario: str | None = None
    mqtt_clave: str | None = None

    # US-20: el equipo se considera desconectado si pasa este tiempo sin ningun mensaje suyo
    # (manda un latido cada 30 s, asi que 90 s = 3 latidos perdidos)
    equipo_timeout_segundos: int = 90

    # Login (US-01 y US-07)
    sesion_minutos: int = 15  # la sesion se cierra tras estos minutos sin actividad
    login_intentos_max: int = 5  # intentos fallidos seguidos antes de bloquear la cuenta
    login_bloqueo_minutos: int = 15
    bcrypt_rondas: int = 12  # costo del hash de contrasenas (los tests usan menos, para ir rapido)
    # La cookie de sesion solo viaja por HTTPS. En desarrollo es false porque la web va por http
    cookie_segura: bool = False

    # Recuperacion de contrasena (US-08)
    recuperacion_minutos: int = 30  # vencimiento del link que llega por mail
    web_url: str = "http://localhost:5173"  # para armar el link del mail
    # Sin SMTP_HOST el mail no se envia: el link se muestra en la consola del servidor
    smtp_host: str | None = None
    smtp_puerto: int = 587
    smtp_usuario: str | None = None
    smtp_clave: str | None = None
    smtp_remitente: str | None = None  # por defecto, smtp_usuario


config = Config()
