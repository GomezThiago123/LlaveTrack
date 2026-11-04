"""US-16: aviso automatico al docente que no devolvio la llave.

Al pedir la llave, el docente dice hasta que hora usa el aula. Si RECORDATORIO_MINUTOS (15)
despues sigue sin devolverla, le llega un mail; si pasan DEMORADA_MINUTOS (60), el preceptor la ve
"Demorada". El mail lo manda un hilo del servidor que revisa cada minuto (app/tareas.py): es la
unica tarea periodica, porque un mail no puede esperar a que alguien abra la web.

Como el resto de app/servicios, no hace commit: lo hace quien la llama.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import config
from app.modelos import Llave, Prestamo


def avisos_pendientes(sesion: Session, ahora: datetime) -> list[Prestamo]:
    """Los prestamos que ya tienen que recibir el aviso. Los marca como avisados: el mail lo manda
    quien llama, despues del commit (asi nunca sale dos veces aunque falle algo)."""
    limite = ahora - timedelta(minutes=config.recordatorio_minutos)
    lista = list(
        sesion.scalars(
            select(Prestamo)
            .options(joinedload(Prestamo.usuario), joinedload(Prestamo.llave).joinedload(Llave.aula))
            .where(
                Prestamo.devuelto_en.is_(None),
                Prestamo.hora_fin.is_not(None),
                Prestamo.hora_fin <= limite,
                Prestamo.aviso_automatico_en.is_(None),
            )
        )
    )
    for prestamo in lista:
        prestamo.aviso_automatico_en = ahora
    return lista


def demorada(prestamo: Prestamo, ahora: datetime) -> bool:
    """Sigue sin devolver DEMORADA_MINUTOS despues de la hora hasta la que iba a usar el aula."""
    return (
        prestamo.devuelto_en is None
        and prestamo.hora_fin is not None
        and ahora >= prestamo.hora_fin + timedelta(minutes=config.demorada_minutos)
    )
