"""Prestamos: los del docente (US-17), el historial del preceptor (US-12 y US-13) y el
recordatorio de devolucion (US-16).

US-16 pide un aviso automatico al terminar el turno del docente, pero el sistema todavia no
conoce los horarios: por ahora el recordatorio lo manda el preceptor con un boton.

Como el resto de app/servicios, no hace commit: lo hace quien la llama.
"""

from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errores import ErrorNegocio
from app.modelos import Llave, Prestamo, Usuario
from app.tipos import ZONA_ARGENTINA, ahora_utc

FiltroEstado = Literal["todos", "abiertos", "devueltos"]


def mis_prestamos(sesion: Session, usuario: Usuario, limite: int = 50) -> list[Prestamo]:
    """Los prestamos del usuario: primero los que todavia tiene, despues los mas nuevos."""
    return list(
        sesion.scalars(
            select(Prestamo)
            .where(Prestamo.usuario_id == usuario.id)
            .order_by(Prestamo.devuelto_en.is_not(None), Prestamo.retirado_en.desc())
            .limit(limite)
        )
    )


def historial(
    sesion: Session,
    aula_id: int | None = None,
    usuario_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    estado: FiltroEstado = "todos",
    limite: int = 500,
) -> list[Prestamo]:
    """Retiros y devoluciones con filtros, del mas nuevo al mas viejo.

    desde y hasta son dias de Argentina e incluyen el dia completo.
    """
    consulta = select(Prestamo).join(Llave).order_by(Prestamo.retirado_en.desc()).limit(limite)
    if aula_id is not None:
        consulta = consulta.where(Llave.aula_id == aula_id)
    if usuario_id is not None:
        consulta = consulta.where(Prestamo.usuario_id == usuario_id)
    if desde is not None:
        consulta = consulta.where(Prestamo.retirado_en >= _inicio_del_dia(desde))
    if hasta is not None:
        consulta = consulta.where(Prestamo.retirado_en < _inicio_del_dia(hasta + timedelta(days=1)))
    if estado == "abiertos":
        consulta = consulta.where(Prestamo.devuelto_en.is_(None))
    elif estado == "devueltos":
        consulta = consulta.where(Prestamo.devuelto_en.is_not(None))
    return list(sesion.scalars(consulta))


def llaves_en_poder(sesion: Session, usuario_id: int) -> int:
    """Cuantas llaves tiene hoy el docente (US-13: se muestra arriba del historial)."""
    return sesion.scalar(
        select(func.count()).select_from(Prestamo).where(
            Prestamo.usuario_id == usuario_id, Prestamo.devuelto_en.is_(None)
        )
    )


def marcar_recordatorio(sesion: Session, prestamo_id: int, ahora: datetime | None = None) -> Prestamo:
    """Registra que se mando un recordatorio. El mail lo manda la ruta despues del commit."""
    prestamo = sesion.get(Prestamo, prestamo_id)
    if prestamo is None:
        raise ErrorNegocio(404, "PRESTAMO_NO_ENCONTRADO", "El préstamo no existe.")
    if prestamo.devuelto_en is not None:
        raise ErrorNegocio(409, "PRESTAMO_DEVUELTO", "Esa llave ya fue devuelta.")
    prestamo.recordatorio_enviado_en = ahora or ahora_utc()
    return prestamo


def _inicio_del_dia(dia: date) -> datetime:
    return datetime.combine(dia, time(0, 0), tzinfo=ZONA_ARGENTINA)
