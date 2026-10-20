from sqlalchemy import select

from app.modelos import Aula, EstadoLlave, Incidente, Llave, Usuario
from app.seed import borrar_todo


def test_seed_carga_aulas_con_llave_disponible(sesion):
    aulas = sesion.scalars(select(Aula)).all()
    assert len(aulas) == 5
    llaves = sesion.scalars(select(Llave)).all()
    assert all(llave.estado == EstadoLlave.DISPONIBLE for llave in llaves)


def test_seed_guarda_emails_en_minusculas(sesion):
    emails = sesion.scalars(select(Usuario.email)).all()
    assert all(email == email.lower() for email in emails)


def test_seed_real_es_valido():
    """seed/datos.json (el que se carga con python -m app.seed) no tiene UID ni slots repetidos."""
    import json
    import re

    from app.seed import ARCHIVO_DATOS

    datos = json.loads(ARCHIVO_DATOS.read_text(encoding="utf-8"))
    equipo = datos["dispositivos"][0]
    llaves = [a["llave"] for a in datos["aulas"]]
    uids = [llave["rfidUid"] for llave in llaves]
    slots = [llave["slot"] for llave in llaves]

    assert len(datos["aulas"]) == 30
    assert all(re.fullmatch(r"[0-9A-F]+", uid) for uid in uids)  # hex en mayusculas sin separadores
    assert len(set(uids)) == len(uids)
    assert len(set(slots)) == len(slots)
    # Ninguna llave en un slot reservado (el 0 es del tag HOME) ni fuera del disco
    assert all(0 <= s < equipo["slotsTotales"] and s not in equipo["slotsReservados"] for s in slots)


def test_reiniciar_borra_todo_aunque_haya_incidentes(sesion):
    # Un incidente apunta a un aula y a un usuario: hay que borrarlo antes que ellos
    aula = sesion.scalars(select(Aula)).first()
    usuario = sesion.scalars(select(Usuario)).first()
    sesion.add(Incidente(device_id="equipo-01", tipo="MOTOR_NO_GIRA", aula_id=aula.id, usuario_id=usuario.id))
    sesion.flush()
    borrar_todo(sesion)
    sesion.flush()
    assert sesion.scalars(select(Aula)).all() == []
