"""Tests del armado de pantallas del LCD del simulador (la regla que copia el firmware, US-23)."""

from argparse import Namespace

from simulador.simulador import LCD_ANCHO, Equipo, mqtt, pantallas_reposo

HORA = "Mar 20/10  14:32"


def opciones(**cambios) -> Namespace:
    datos = dict(equipo="equipo-01", host="localhost", puerto=1883, slots=32, repetir=False, tls=False, usuario=None, clave=None)
    return Namespace(**{**datos, **cambios})


def test_contra_la_nube_usa_tls_usuario_y_clave(monkeypatch):
    tls, credenciales = [], []
    monkeypatch.setattr(mqtt.Client, "tls_set", lambda self, *a, **k: tls.append(True))
    monkeypatch.setattr(mqtt.Client, "username_pw_set", lambda self, u, c: credenciales.append((u, c)))
    Equipo(opciones(tls=True, usuario="equipo-01", clave="secreta", puerto=8883))
    assert tls == [True] and credenciales == [("equipo-01", "secreta")]


def test_en_desarrollo_no_usa_tls_ni_usuario(monkeypatch):
    llamadas = []
    monkeypatch.setattr(mqtt.Client, "tls_set", lambda self, *a, **k: llamadas.append("tls"))
    monkeypatch.setattr(mqtt.Client, "username_pw_set", lambda self, u, c: llamadas.append("usuario"))
    Equipo(opciones())
    assert llamadas == []


def test_sin_faltantes_solo_la_hora():
    assert pantallas_reposo(HORA, []) == [HORA]


def test_entran_dos_aulas_por_pantalla():
    assert pantallas_reposo(HORA, ["105", "114", "204"]) == [HORA, "Faltan: 105 114", "Faltan: 204"]


def test_ninguna_pantalla_pasa_de_16_caracteres():
    aulas = [str(n) for n in range(101, 131)]  # 30 aulas: el peor caso
    pantallas = pantallas_reposo(HORA, aulas)
    assert all(len(p) <= LCD_ANCHO for p in pantallas)
    # Estan todas, en orden
    mostradas = " ".join(p.removeprefix("Faltan: ") for p in pantallas[1:]).split()
    assert mostradas == aulas


def test_un_nombre_largo_va_solo_y_recortado():
    pantallas = pantallas_reposo(HORA, ["105", "Laboratorio de Robotica", "214"])
    assert pantallas == [HORA, "Faltan: 105", "Laboratorio de R", "Faltan: 214"]
