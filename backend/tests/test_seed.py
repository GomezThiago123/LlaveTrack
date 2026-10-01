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
