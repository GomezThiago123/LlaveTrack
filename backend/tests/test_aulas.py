"""Tests de consulta de aulas (US-02)."""

from datetime import timedelta

from sqlalchemy import select, update

from app.modelos import Aula, Dispositivo, EstadoLlave, EstadoReserva, Llave, Prestamo, Reserva, Usuario
from app.servicios import reservas
from app.tipos import ahora_utc

ANA = "ana.perez@example.com"
BRUNO = "bruno.gomez@example.com"
CARLA_PRECEPTORA = "carla.diaz@example.com"


def preparar(fabrica_sesiones):
    """Deja el aula 214 reservada por Ana y el aula 215 prestada a Bruno."""
    with fabrica_sesiones() as s:
        ana = s.scalar(select(Usuario).where(Usuario.email == ANA))
        bruno = s.scalar(select(Usuario).where(Usuario.email == BRUNO))
        aula_214 = s.scalar(select(Aula).where(Aula.nombre == "214"))
        aula_215 = s.scalar(select(Aula).where(Aula.nombre == "215"))
        reservas.crear_reserva(s, ana, aula_214.id)
        # El retiro real llega en la Fase 1B (MQTT); aca se arma el prestamo a mano
        reserva_bruno = reservas.crear_reserva(s, bruno, aula_215.id)
        reserva_bruno.estado = EstadoReserva.USADA
        reserva_bruno.llave.estado = EstadoLlave.PRESTADA
        reserva_bruno.llave.slot = None
        s.add(Prestamo(llave_id=reserva_bruno.llave_id, usuario_id=bruno.id, reserva_id=reserva_bruno.id))
        s.commit()


def por_nombre(lista):
    return {aula["nombre"]: aula for aula in lista}


def test_estado_publico_sin_login_y_sin_datos_personales(cliente, fabrica_sesiones):
    preparar(fabrica_sesiones)
    res = cliente.get("/api/publico/estado")
    assert res.status_code == 200
    datos = res.json()
    assert datos["equipoOnline"] is False
    aulas = por_nombre(datos["aulas"])
    assert aulas["214"]["estado"] == "RESERVADA"
    assert aulas["215"]["estado"] == "PRESTADA"
    assert aulas["216"]["estado"] == "DISPONIBLE"
    assert all(set(aula) == {"id", "nombre", "estado"} for aula in datos["aulas"])
    assert "Perez" not in res.text and "5555" not in res.text


def test_estado_publico_muestra_equipo_online(cliente, fabrica_sesiones):
    with fabrica_sesiones() as s:
        s.execute(update(Dispositivo).values(online=True))
        s.commit()
    assert cliente.get("/api/publico/estado").json()["equipoOnline"] is True


def test_estado_publico_no_muestra_llaves_dadas_de_baja(cliente, fabrica_sesiones):
    with fabrica_sesiones() as s:
        s.execute(update(Llave).where(Llave.rfid_uid == "04E5F6A7").values(estado=EstadoLlave.BAJA))
        s.commit()
    nombres = [aula["nombre"] for aula in cliente.get("/api/publico/estado").json()["aulas"]]
    assert "Taller" not in nombres and len(nombres) == 4


def test_reserva_vencida_aparece_disponible(cliente, fabrica_sesiones):
    preparar(fabrica_sesiones)
    with fabrica_sesiones() as s:
        s.execute(
            update(Reserva)
            .where(Reserva.estado == EstadoReserva.PENDIENTE)
            .values(expira_en=ahora_utc() - timedelta(minutes=1))
        )
        s.commit()
    aulas = por_nombre(cliente.get("/api/publico/estado").json()["aulas"])
    assert aulas["214"]["estado"] == "DISPONIBLE"


def test_docente_no_ve_quien_tiene_las_llaves(cliente, fabrica_sesiones):
    preparar(fabrica_sesiones)
    res = cliente.get("/api/aulas", headers={"X-Usuario-Email": ANA})
    assert res.status_code == 200
    assert all(aula["tenedor"] is None for aula in res.json())


def test_preceptor_ve_quien_tiene_cada_llave_y_su_telefono(cliente, fabrica_sesiones):
    preparar(fabrica_sesiones)
    aulas = por_nombre(cliente.get("/api/aulas", headers={"X-Usuario-Email": CARLA_PRECEPTORA}).json())

    assert aulas["214"]["tenedor"]["apellido"] == "Perez"  # reservada
    assert aulas["215"]["tenedor"]["apellido"] == "Gomez"  # prestada
    assert aulas["215"]["tenedor"]["telefono"] == "11 5555-0002"
    assert aulas["216"]["tenedor"] is None  # disponible


def test_lista_de_aulas_requiere_login(cliente):
    res = cliente.get("/api/aulas")
    assert res.status_code == 401
    assert res.json()["error"]["codigo"] == "NO_AUTENTICADO"
