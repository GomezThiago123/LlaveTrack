"""Tests de lo que agrega el rediseño: mis prestamos (US-17), historial (US-12/13),
recordatorio (US-16), gestion de docentes (US-09), equipo y tags RFID (US-10)."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app import correo
from app.modelos import Aula, EstadoLlave, Llave, Prestamo, Reserva, Usuario
from app.tipos import ZONA_ARGENTINA, ahora_utc

ANA = "ana.perez@example.com"
BRUNO = "bruno.gomez@example.com"
CARLA_PRECEPTORA = "carla.diaz@example.com"
CLAVE = "llavetrack"  # la de tests/datos_prueba.json


@pytest.fixture
def mails(monkeypatch):
    """Junta los mails que se mandarian, en lugar de mandarlos."""
    enviados = []
    monkeypatch.setattr(correo, "enviar_correo", lambda *args: enviados.append(args))
    return enviados


def prestar(fabrica_sesiones, email, aula, hace=timedelta(hours=1), devuelto_hace=None) -> int:
    """Crea un prestamo (abierto, o devuelto hace `devuelto_hace`) y devuelve su id."""
    with fabrica_sesiones() as s:
        usuario = s.scalar(select(Usuario).where(Usuario.email == email))
        llave = s.scalar(select(Llave).join(Aula).where(Aula.nombre == aula))
        ahora = ahora_utc()
        reserva = Reserva(
            usuario_id=usuario.id, llave_id=llave.id, codigo="000000", creada_en=ahora - hace,
            expira_en=ahora - hace, estado="USADA",
        )
        s.add(reserva)
        s.flush()
        prestamo = Prestamo(
            llave_id=llave.id, usuario_id=usuario.id, reserva_id=reserva.id, retirado_en=ahora - hace,
            devuelto_en=ahora - devuelto_hace if devuelto_hace else None,
        )
        s.add(prestamo)
        if devuelto_hace is None:
            llave.estado, llave.slot = EstadoLlave.PRESTADA, None
        s.commit()
        return prestamo.id


def id_de(fabrica_sesiones, email) -> int:
    with fabrica_sesiones() as s:
        return s.scalar(select(Usuario.id).where(Usuario.email == email))


# --- Mis prestamos (US-17) ---


def test_mis_prestamos_primero_los_que_tengo(cliente, ingresar, fabrica_sesiones):
    prestar(fabrica_sesiones, ANA, "215", hace=timedelta(days=1), devuelto_hace=timedelta(hours=20))
    prestar(fabrica_sesiones, ANA, "214", hace=timedelta(hours=2))
    prestar(fabrica_sesiones, BRUNO, "216")
    ingresar(ANA)

    mios = cliente.get("/api/prestamos/mios").json()
    assert [p["aula"] for p in mios] == ["214", "215"]  # el abierto primero; el de Bruno no aparece
    assert mios[0]["devueltoEn"] is None and mios[1]["devueltoEn"] is not None


def test_mis_prestamos_vacio(cliente, ingresar):
    ingresar(ANA)
    assert cliente.get("/api/prestamos/mios").json() == []


def test_tenedor_trae_su_id_para_saber_si_es_mio(cliente, ingresar, fabrica_sesiones):
    prestar(fabrica_sesiones, ANA, "214")
    ingresar(ANA)
    aula = next(a for a in cliente.get("/api/aulas").json() if a["nombre"] == "214")
    assert aula["tenedor"]["usuarioId"] == id_de(fabrica_sesiones, ANA)


# --- Historial (US-12 y US-13) ---


def test_historial_es_solo_para_el_preceptor(cliente, ingresar):
    ingresar(ANA)
    assert cliente.get("/api/prestamos").status_code == 403


def test_historial_filtra_por_aula_docente_y_estado(cliente, ingresar, fabrica_sesiones):
    prestar(fabrica_sesiones, ANA, "214", hace=timedelta(hours=3), devuelto_hace=timedelta(hours=2))
    prestar(fabrica_sesiones, ANA, "215")
    prestar(fabrica_sesiones, BRUNO, "216")
    ingresar(CARLA_PRECEPTORA)
    with fabrica_sesiones() as s:
        id_214 = s.scalar(select(Aula.id).where(Aula.nombre == "214"))

    todos = cliente.get("/api/prestamos").json()
    assert len(todos["prestamos"]) == 3 and todos["enPoder"] is None

    por_aula = cliente.get("/api/prestamos", params={"aulaId": id_214}).json()["prestamos"]
    assert [p["aula"] for p in por_aula] == ["214"]

    de_ana = cliente.get("/api/prestamos", params={"usuarioId": id_de(fabrica_sesiones, ANA)}).json()
    assert len(de_ana["prestamos"]) == 2
    assert de_ana["enPoder"] == 1  # US-13: cuantas llaves tiene hoy

    abiertos = cliente.get("/api/prestamos", params={"estado": "abiertos"}).json()["prestamos"]
    assert {p["aula"] for p in abiertos} == {"215", "216"}
    devueltos = cliente.get("/api/prestamos", params={"estado": "devueltos"}).json()["prestamos"]
    assert [p["aula"] for p in devueltos] == ["214"]
    assert devueltos[0]["docente"]["email"] == ANA


def test_historial_filtra_por_dias_de_argentina(cliente, ingresar, fabrica_sesiones):
    prestar(fabrica_sesiones, ANA, "214", hace=timedelta(days=3), devuelto_hace=timedelta(days=3) - timedelta(hours=1))
    prestar(fabrica_sesiones, ANA, "215", hace=timedelta(minutes=5))
    ingresar(CARLA_PRECEPTORA)
    hoy = ahora_utc().astimezone(ZONA_ARGENTINA).date()

    de_hoy = cliente.get("/api/prestamos", params={"desde": hoy.isoformat(), "hasta": hoy.isoformat()}).json()
    assert [p["aula"] for p in de_hoy["prestamos"]] == ["215"]
    hace_una_semana = (hoy - timedelta(days=7)).isoformat()
    hasta_ayer = (hoy - timedelta(days=1)).isoformat()
    viejos = cliente.get("/api/prestamos", params={"desde": hace_una_semana, "hasta": hasta_ayer}).json()
    assert [p["aula"] for p in viejos["prestamos"]] == ["214"]


# --- Recordatorio (US-16) ---


def test_recordatorio_manda_mail_y_queda_registrado(cliente, ingresar, fabrica_sesiones, mails):
    prestamo_id = prestar(fabrica_sesiones, ANA, "214")
    ingresar(CARLA_PRECEPTORA)

    res = cliente.post(f"/api/prestamos/{prestamo_id}/recordatorio")
    assert res.status_code == 200 and res.json()["recordatorioEnviadoEn"] is not None
    (destino, asunto, cuerpo), = mails
    assert destino == ANA and "214" in asunto and "tecla B" in cuerpo


def test_recordatorio_de_llave_devuelta_da_409(cliente, ingresar, fabrica_sesiones, mails):
    prestamo_id = prestar(fabrica_sesiones, ANA, "214", devuelto_hace=timedelta(minutes=10))
    ingresar(CARLA_PRECEPTORA)
    res = cliente.post(f"/api/prestamos/{prestamo_id}/recordatorio")
    assert res.status_code == 409 and res.json()["error"]["codigo"] == "PRESTAMO_DEVUELTO"
    assert mails == []


def test_docente_no_manda_recordatorios(cliente, ingresar, fabrica_sesiones):
    prestamo_id = prestar(fabrica_sesiones, BRUNO, "214")
    ingresar(ANA)
    assert cliente.post(f"/api/prestamos/{prestamo_id}/recordatorio").status_code == 403


# --- Gestion de docentes (US-09) ---


def test_alta_de_docente_con_link_para_crear_la_contrasena(cliente, ingresar, mails):
    ingresar(CARLA_PRECEPTORA)
    res = cliente.post(
        "/api/usuarios",
        json={"nombre": "Diego", "apellido": "Ruiz", "email": "Diego.Ruiz@Example.com", "telefono": "11 5555-0009"},
    )
    assert res.status_code == 201
    nuevo = res.json()
    assert nuevo["email"] == "diego.ruiz@example.com" and nuevo["rol"] == "DOCENTE"
    assert nuevo["activo"] is True and nuevo["tieneClave"] is False

    (destino, asunto, cuerpo), = mails
    assert destino == "diego.ruiz@example.com" and "contraseña" in asunto
    token = cuerpo.split("token=")[1].split()[0]
    assert cliente.post("/api/auth/restablecer", json={"token": token, "claveNueva": "clave-nueva-1"}).status_code == 204
    login = cliente.post("/api/auth/login", json={"email": "diego.ruiz@example.com", "clave": "clave-nueva-1"})
    assert login.status_code == 200


def test_no_se_puede_cargar_dos_veces_el_mismo_email(cliente, ingresar, mails):
    ingresar(CARLA_PRECEPTORA)
    res = cliente.post("/api/usuarios", json={"nombre": "Otra", "apellido": "Ana", "email": "ANA.PEREZ@example.com"})
    assert res.status_code == 409 and res.json()["error"]["codigo"] == "EMAIL_REPETIDO"
    assert mails == []


def test_desactivado_no_entra_y_se_le_cierra_la_sesion(cliente, fabrica_sesiones):
    from fastapi.testclient import TestClient

    from app.main import app

    bruno = TestClient(app)
    assert bruno.post("/api/auth/login", json={"email": BRUNO, "clave": CLAVE}).status_code == 200
    cliente.post("/api/auth/login", json={"email": CARLA_PRECEPTORA, "clave": CLAVE})

    id_bruno = id_de(fabrica_sesiones, BRUNO)
    res = cliente.patch(f"/api/usuarios/{id_bruno}", json={"activo": False})
    assert res.status_code == 200 and res.json()["activo"] is False
    assert bruno.get("/api/auth/yo").status_code == 401  # la sesion abierta se cerro
    assert bruno.post("/api/auth/login", json={"email": BRUNO, "clave": CLAVE}).status_code == 401

    cliente.patch(f"/api/usuarios/{id_bruno}", json={"activo": True})
    assert bruno.post("/api/auth/login", json={"email": BRUNO, "clave": CLAVE}).status_code == 200


def test_no_puede_desactivarse_a_si_mismo(cliente, ingresar, fabrica_sesiones):
    ingresar(CARLA_PRECEPTORA)
    res = cliente.patch(f"/api/usuarios/{id_de(fabrica_sesiones, CARLA_PRECEPTORA)}", json={"activo": False})
    assert res.status_code == 409 and res.json()["error"]["codigo"] == "NO_PUEDE_DESACTIVARSE"


def test_docente_no_gestiona_usuarios(cliente, ingresar):
    ingresar(ANA)
    assert cliente.get("/api/usuarios").status_code == 403
    assert cliente.post("/api/usuarios", json={"nombre": "X", "apellido": "Y", "email": "x@y.com"}).status_code == 403


def test_listado_de_usuarios(cliente, ingresar):
    ingresar(CARLA_PRECEPTORA)
    usuarios = cliente.get("/api/usuarios").json()
    assert {u["email"] for u in usuarios} >= {ANA, BRUNO, CARLA_PRECEPTORA}
    assert all(u["tieneClave"] for u in usuarios)


def test_yo_trae_el_telefono(cliente, ingresar):
    ingresar(ANA)
    assert cliente.get("/api/auth/yo").json()["telefono"] == "11 5555-0001"


# --- Equipo y tags RFID (US-10) ---


def test_estado_del_equipo_con_sus_llaves(cliente, ingresar, fabrica_sesiones):
    prestar(fabrica_sesiones, ANA, "214")
    ingresar(CARLA_PRECEPTORA)
    equipo = cliente.get("/api/equipo").json()
    assert equipo["deviceId"] == "equipo-01" and equipo["online"] is True
    assert equipo["slotsReservados"] == [0]
    llaves = {llave["aula"]: llave for llave in equipo["llaves"]}
    assert llaves["214"]["estado"] == "PRESTADA" and llaves["214"]["slot"] is None
    assert llaves["215"]["slot"] == 2 and llaves["215"]["rfidUid"] == "04B2C3D4"


def test_cambiar_el_tag_de_un_aula(cliente, ingresar, fabrica_sesiones):
    ingresar(CARLA_PRECEPTORA)
    with fabrica_sesiones() as s:
        id_215 = s.scalar(select(Llave.id).join(Aula).where(Aula.nombre == "215"))

    res = cliente.put(f"/api/llaves/{id_215}/rfid", json={"rfidUid": "de:ad:be:ef"})
    assert res.status_code == 200 and res.json()["rfidUid"] == "DEADBEEF"

    repetido = cliente.put(f"/api/llaves/{id_215}/rfid", json={"rfidUid": "04A1B2C3"})  # el del 214
    assert repetido.status_code == 409
    assert repetido.json()["error"]["mensaje"] == "Este tag ya pertenece al aula 214."

    invalido = cliente.put(f"/api/llaves/{id_215}/rfid", json={"rfidUid": "hola"})
    assert invalido.status_code == 422 and invalido.json()["error"]["codigo"] == "UID_INVALIDO"


def test_docente_no_ve_el_equipo_ni_cambia_tags(cliente, ingresar, fabrica_sesiones):
    ingresar(ANA)
    with fabrica_sesiones() as s:
        s.execute(update(Llave).values(estado=EstadoLlave.DISPONIBLE))
        id_llave = s.scalar(select(Llave.id))
    assert cliente.get("/api/equipo").status_code == 403
    assert cliente.put(f"/api/llaves/{id_llave}/rfid", json={"rfidUid": "DEADBEEF"}).status_code == 403
