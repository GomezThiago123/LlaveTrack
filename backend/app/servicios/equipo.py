"""Reglas de lo que pasa en el equipo: inicio, retiro (US-04/05) y devolucion (US-06).

No sabe nada de MQTT: recibe datos ya validados y devuelve los datos de la respuesta.
Si algo se rechaza, lanza RechazoEquipo con un motivo del protocolo (docs/protocolo-mqtt.md).
Como en app/servicios/reservas.py, no hace commit: lo hace quien la llama.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import config
from app.modelos import (
    Aula,
    Dispositivo,
    EstadoLlave,
    EstadoReserva,
    Llave,
    Prestamo,
    Reserva,
    Usuario,
)
from app import correo
from app.errores import ErrorNegocio
from app.servicios.reservas import _cerrar_reserva, crear_reserva, vencer_reservas
from app.tipos import ahora_utc


# Clave de sesion.info: acciones para hacer recien despues del commit (ej. mandar un mail).
# Las ejecuta app/protocolo.py; si el evento se rechaza o falla, no se hacen.
DESPUES_DEL_COMMIT = "despues_del_commit"


def _despues_del_commit(sesion: Session, accion) -> None:
    sesion.info.setdefault(DESPUES_DEL_COMMIT, []).append(accion)


def _usuario_por_dni(sesion: Session, dni: str) -> Usuario:
    """US-18 y US-20: el docente que escribio su DNI en el teclado. Desactivado = no reconocido."""
    usuario = sesion.scalar(select(Usuario).where(Usuario.dni == dni, Usuario.activo.is_(True)))
    if usuario is None:
        raise RechazoEquipo("CREDENCIAL_NO_RECONOCIDA")
    return usuario


class RechazoEquipo(Exception):
    """El servidor rechaza el evento. motivo: CODIGO_INVALIDO, CODIGO_VENCIDO, etc."""

    def __init__(self, motivo: str, **datos):
        super().__init__(motivo)
        self.motivo = motivo
        self.datos = datos  # van en la respuesta (ej. US-20: aula y quien la retiro)


def inicio(sesion: Session, device_id: str, slots_totales: int, slots_reservados: list[int]) -> dict:
    """El equipo arranco: guarda su configuracion y le dice en que slot vacio quedarse."""
    dispositivo = sesion.scalar(select(Dispositivo).where(Dispositivo.device_id == device_id))
    if dispositivo is None:
        dispositivo = Dispositivo(device_id=device_id, slots_totales=slots_totales)
        sesion.add(dispositivo)
    dispositivo.slots_totales = slots_totales
    dispositivo.slots_reservados = slots_reservados
    dispositivo.online = True
    dispositivo.ultimo_contacto = ahora_utc()
    sesion.flush()
    # Despues del homing el disco esta en el slot 0: el vacio mas cercano es el que menos gira
    return {"slotReposo": _slot_vacio_mas_cercano(sesion, dispositivo, a=0)}


def solicitud_retiro(
    sesion: Session,
    codigo: str | None,
    ahora: datetime | None = None,
    dni: str | None = None,
    aula: str | None = None,
) -> dict:
    """El docente ingreso un codigo (o su DNI, US-18). Si es valido, dice que llave entregar y donde
    esta. La respuesta trae el codigo (con DNI, el equipo lo necesita para confirmar el retiro) y el
    nombre, para el LCD: "Hola Ana / Aula 214"."""
    ahora = ahora or ahora_utc()
    vencer_reservas(sesion, ahora)

    if dni is not None:
        usuario = _usuario_por_dni(sesion, dni)
        reserva = sesion.scalar(
            select(Reserva).where(Reserva.usuario_id == usuario.id, Reserva.estado == EstadoReserva.PENDIENTE)
        )
        if aula is not None:
            reserva = _reservar_desde_el_teclado(sesion, usuario, aula, reserva, ahora)
        if reserva is None:
            raise RechazoEquipo("SIN_RESERVA")
        codigo = reserva.codigo
    else:
        reserva = _reserva_pendiente(sesion, codigo)
    if reserva is None:
        ultima = sesion.scalar(
            select(Reserva).where(Reserva.codigo == codigo).order_by(Reserva.id.desc())
        )
        vencida = ultima is not None and ultima.estado == EstadoReserva.VENCIDA
        raise RechazoEquipo("CODIGO_VENCIDO" if vencida else "CODIGO_INVALIDO")

    llave = reserva.llave
    if llave.slot is None:  # no deberia pasar: una llave reservada esta colgada en el disco
        raise RechazoEquipo("ERROR_INTERNO")

    # Que no venza mientras el disco gira y el docente retira la llave
    minimo = ahora + timedelta(seconds=config.retiro_margen_segundos)
    if reserva.expira_en < minimo:
        reserva.expira_en = minimo

    return {
        "slot": llave.slot,
        "uid": llave.rfid_uid,
        "aula": llave.aula.nombre,
        "apellido": reserva.usuario.apellido,
        "nombre": reserva.usuario.nombre,
        "codigo": codigo,
    }


def _reservar_desde_el_teclado(
    sesion: Session, usuario: Usuario, nombre_aula: str, pendiente: Reserva | None, ahora: datetime
) -> Reserva:
    """El docente olvido el celular: con su DNI pide el aula en el teclado y se reserva ahi mismo.
    Si ya tenia esa misma aula reservada (ej. desde la web), se usa esa reserva."""
    aula = sesion.scalar(select(Aula).where(Aula.nombre == nombre_aula))
    if aula is None:
        raise RechazoEquipo("AULA_NO_ENCONTRADA")
    if pendiente is not None:
        if pendiente.llave.aula_id == aula.id:
            return pendiente
        raise RechazoEquipo("YA_TIENE_RESERVA")
    try:
        return crear_reserva(sesion, usuario, aula.id, ahora)
    except ErrorNegocio as error:  # LLAVE_NO_DISPONIBLE, AULA_EN_REVISION...
        raise RechazoEquipo(error.codigo) from error


def retiro_confirmado(sesion: Session, codigo: str, uid: str, slot: int) -> dict:
    """El docente se llevo la llave: la reserva se usa y empieza el prestamo.

    slot es donde estaba la llave realmente (puede no coincidir si el equipo tuvo que buscarla).
    Ese slot queda vacio y pasa a ser la posicion de reposo del disco.
    """
    reserva = _reserva_pendiente(sesion, codigo)
    if reserva is None or reserva.llave.rfid_uid != uid:
        raise RechazoEquipo("CODIGO_INVALIDO")

    # UPDATEs condicionales, igual que en las reservas: solo si nadie los cambio antes
    reserva_usada = sesion.execute(
        update(Reserva)
        .where(Reserva.id == reserva.id, Reserva.estado == EstadoReserva.PENDIENTE)
        .values(estado=EstadoReserva.USADA)
    ).rowcount
    llave_prestada = sesion.execute(
        update(Llave)
        .where(Llave.id == reserva.llave_id, Llave.estado == EstadoLlave.RESERVADA)
        .values(estado=EstadoLlave.PRESTADA, slot=None)
    ).rowcount
    if reserva_usada != 1 or llave_prestada != 1:
        raise RechazoEquipo("ERROR_INTERNO")

    sesion.add(
        Prestamo(
            llave_id=reserva.llave_id,
            usuario_id=reserva.usuario_id,
            reserva_id=reserva.id,
            retirado_en=ahora_utc(),
            hora_fin=reserva.hora_fin,  # US-16
        )
    )
    return {}


def devolucion(
    sesion: Session,
    device_id: str,
    uid: str,
    slot: int,
    dni: str | None = None,
    confirmada: bool = False,
    devuelto_en: int | None = None,
    ahora: datetime | None = None,
) -> dict:
    """Se colgo una llave en el slot de la ventana: se cierra su prestamo.

    US-20: si quien devuelve escribio su DNI y no es quien la retiro, primero se rechaza con
    CONFIRMAR_TERCERO (el LCD muestra quien la tenia); al confirmar, queda "devuelta por" y se le
    avisa por mail al que la tenia.
    US-14: `devuelto_en` es la hora real de una devolucion hecha sin conexion (la del equipo).
    """
    ahora = ahora or ahora_utc()
    llave = sesion.scalar(select(Llave).where(Llave.rfid_uid == uid))
    if llave is None:
        raise RechazoEquipo("LLAVE_DESCONOCIDA")
    prestamo = sesion.scalar(
        select(Prestamo).where(Prestamo.llave_id == llave.id, Prestamo.devuelto_en.is_(None))
    )
    if prestamo is None or llave.estado != EstadoLlave.PRESTADA:
        raise RechazoEquipo("SIN_PRESTAMO_ACTIVO")

    tercero = None
    if dni is not None:
        quien = _usuario_por_dni(sesion, dni)
        if quien.id != prestamo.usuario_id:
            if not confirmada:
                raise RechazoEquipo("CONFIRMAR_TERCERO", aula=llave.aula.nombre, retiradaPor=prestamo.usuario.apellido)
            tercero = quien

    momento = ahora
    if devuelto_en is not None:
        # US-14: la hora del equipo, si es razonable (entre el retiro y ahora, con margen por si su
        # reloj adelanta un poco). Si no, la de ahora.
        hora_equipo = datetime.fromtimestamp(devuelto_en, UTC)
        if prestamo.retirado_en <= hora_equipo <= ahora + timedelta(minutes=5):
            momento = min(hora_equipo, ahora)

    prestamo_cerrado = sesion.execute(
        update(Prestamo)
        .where(Prestamo.id == prestamo.id, Prestamo.devuelto_en.is_(None))
        .values(devuelto_en=momento, devuelto_por_id=tercero.id if tercero else None)
    ).rowcount
    llave_disponible = sesion.execute(
        update(Llave)
        .where(Llave.id == llave.id, Llave.estado == EstadoLlave.PRESTADA)
        .values(estado=EstadoLlave.DISPONIBLE, slot=slot)
    ).rowcount
    if prestamo_cerrado != 1 or llave_disponible != 1:
        raise RechazoEquipo("ERROR_INTERNO")
    dispositivo = sesion.scalar(select(Dispositivo).where(Dispositivo.device_id == device_id))
    slot_reposo = _slot_vacio_mas_cercano(sesion, dispositivo, a=slot) if dispositivo else None

    respuesta = {
        "aula": llave.aula.nombre,
        "apellido": prestamo.usuario.apellido,  # quien la retiro
        "slotReposo": slot_reposo,
    }
    if tercero is not None:
        respuesta["devueltaPor"] = tercero.apellido
        titular, aula = prestamo.usuario, llave.aula.nombre
        _despues_del_commit(sesion, lambda: correo.enviar_devuelta_por_otro(titular, aula, tercero, momento))
    return respuesta


def retiro_interrumpido(sesion: Session, codigo: str) -> dict:
    """US-15: se corto la luz durante este retiro y el docente no llego a confirmarlo. La reserva
    se cancela y la llave vuelve a estar disponible. Si ya no estaba pendiente (ej. el retiro si
    se confirmo, o vencio), no cambia nada."""
    reserva = _reserva_pendiente(sesion, codigo)
    if reserva is not None:
        _cerrar_reserva(sesion, reserva, EstadoReserva.CANCELADA)
    return {}


def tag_leido(sesion: Session, device_id: str, uid: str, slot: int) -> dict:
    """US-10, modo alta: el equipo leyo un tag en la ventana. Queda guardado para que el preceptor
    lo vea en la web y lo asocie a un aula. Si el tag ya es de un aula, se lo dice al equipo."""
    dispositivo = sesion.scalar(select(Dispositivo).where(Dispositivo.device_id == device_id))
    if dispositivo is not None:
        dispositivo.ultimo_tag_uid = uid
        dispositivo.ultimo_tag_slot = slot
        dispositivo.ultimo_tag_en = ahora_utc()
    llave = sesion.scalar(select(Llave).where(Llave.rfid_uid == uid))
    return {"aula": llave.aula.nombre if llave else None}


def aulas_faltantes(sesion: Session) -> list[str]:
    """Aulas cuya llave no esta en el disco (US-23): las PRESTADAS, ordenadas por nombre.

    Las RESERVADAS no cuentan: siguen colgadas hasta que el docente las retira.
    El equipo enciende el LED de faltantes y las muestra en el LCD (topico `faltantes`).
    """
    return list(
        sesion.scalars(
            select(Aula.nombre).join(Llave).where(Llave.estado == EstadoLlave.PRESTADA).order_by(Aula.nombre)
        )
    )


def _reserva_pendiente(sesion: Session, codigo: str) -> Reserva | None:
    return sesion.scalar(
        select(Reserva).where(Reserva.codigo == codigo, Reserva.estado == EstadoReserva.PENDIENTE)
    )


def _slot_vacio_mas_cercano(sesion: Session, dispositivo: Dispositivo, a: int) -> int | None:
    """El slot sin llave mas cercano a la posicion `a` (contando que el disco es circular).

    Ocupados: los reservados del equipo (ej. el tag HOME) y los de las llaves colgadas.
    Devuelve None si el disco esta lleno.
    """
    total = dispositivo.slots_totales
    ocupados = set(dispositivo.slots_reservados)
    ocupados |= set(sesion.scalars(select(Llave.slot).where(Llave.slot.is_not(None))))
    vacios = [s for s in range(total) if s not in ocupados]
    if not vacios:
        return None

    def distancia(s: int) -> int:
        d = abs(s - a) % total
        return min(d, total - d)

    return min(vacios, key=lambda s: (distancia(s), s))
