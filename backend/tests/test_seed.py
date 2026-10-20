from sqlalchemy import select

from app.modelos import Aula, EstadoLlave, Llave, Usuario


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
