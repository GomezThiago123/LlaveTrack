"""Carga los datos iniciales desde seed/datos.json.

Uso (desde backend/, con el .venv activado):
    python -m app.seed               carga los datos si la base esta vacia
    python -m app.seed --reiniciar   BORRA todos los datos y los vuelve a cargar
"""

import json
import sys
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import SesionLocal
from app.modelos import (
    Aula,
    Dispositivo,
    EventoDispositivo,
    Llave,
    Prestamo,
    Reserva,
    Rol,
    Usuario,
)

ARCHIVO_DATOS = Path(__file__).parent.parent / "seed" / "datos.json"


def borrar_todo(sesion: Session) -> None:
    # En orden inverso a las dependencias (primero lo que apunta a otras tablas)
    for tabla in (EventoDispositivo, Prestamo, Reserva, Llave, Aula, Usuario, Dispositivo):
        sesion.execute(delete(tabla))


def cargar_datos(sesion: Session, datos: dict) -> None:
    for d in datos["dispositivos"]:
        sesion.add(
            Dispositivo(
                device_id=d["deviceId"],
                slots_totales=d["slotsTotales"],
                slots_reservados=d["slotsReservados"],
            )
        )
    for a in datos["aulas"]:
        aula = Aula(nombre=a["nombre"])
        aula.llaves.append(Llave(rfid_uid=a["llave"]["rfidUid"].upper(), slot=a["llave"]["slot"]))
        sesion.add(aula)
    for u in datos["usuarios"]:
        sesion.add(
            Usuario(
                nombre=u["nombre"],
                apellido=u["apellido"],
                email=u["email"].lower(),
                telefono=u["telefono"],
                rol=Rol(u["rol"]),
            )
        )


def main() -> None:
    reiniciar = "--reiniciar" in sys.argv
    datos = json.loads(ARCHIVO_DATOS.read_text(encoding="utf-8"))

    with SesionLocal() as sesion:
        hay_datos = sesion.scalar(select(func.count()).select_from(Usuario)) > 0
        if hay_datos and not reiniciar:
            print("La base ya tiene datos. Para borrarlos y recargar: python -m app.seed --reiniciar")
            return
        if reiniciar:
            borrar_todo(sesion)
        cargar_datos(sesion, datos)
        sesion.commit()

    print(
        f"Cargados: {len(datos['aulas'])} aulas con su llave, "
        f"{len(datos['usuarios'])} usuarios y {len(datos['dispositivos'])} equipo(s)."
    )


if __name__ == "__main__":
    main()
