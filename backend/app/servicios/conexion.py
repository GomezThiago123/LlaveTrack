"""Si el equipo esta conectado o no (US-22).

El servidor considera online a un equipo solo si:
1. el ultimo mensaje retenido de `estado` dice online (lo pone el equipo al conectar,
   y el broker publica el LWT {"online": false} si se cae), y
2. tuvo contacto hace menos de EQUIPO_TIMEOUT_SEGUNDOS (cualquier evento o el latido
   que manda cada 30 s). Cubre el caso de un `estado` viejo que quedo retenido en el broker.
Ademas, si el servidor pierde la conexion con el broker, marca todos los equipos offline:
sin broker no puede saber nada de ellos (ver app/mqtt_cliente.py).

Como el resto de app/servicios, no hace commit.
"""

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import config
from app.modelos import Dispositivo
from app.tipos import ahora_utc


def equipo_online(sesion: Session, ahora: datetime | None = None) -> bool:
    """True si al menos un equipo esta conectado (en el MVP hay uno solo)."""
    limite = (ahora or ahora_utc()) - timedelta(seconds=config.equipo_timeout_segundos)
    conectado = sesion.scalar(
        select(Dispositivo.id)
        .where(Dispositivo.online, Dispositivo.ultimo_contacto > limite)
        .limit(1)
    )
    return conectado is not None


def registrar_contacto(sesion: Session, device_id: str, online: bool | None = None) -> None:
    """Actualiza ultimo_contacto (y online, si se indica) de un equipo conocido."""
    valores: dict = {"ultimo_contacto": ahora_utc()}
    if online is not None:
        valores["online"] = online
    sesion.execute(update(Dispositivo).where(Dispositivo.device_id == device_id).values(**valores))


def marcar_equipos_offline(sesion: Session) -> None:
    """Todos offline. Se usa cuando el servidor se conecta o se desconecta del broker."""
    sesion.execute(update(Dispositivo).values(online=False))
