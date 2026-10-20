"""Tests del armado de pantallas del LCD del simulador (la regla que copia el firmware, US-21)."""

from simulador.simulador import LCD_ANCHO, pantallas_reposo

HORA = "Mar 20/10  14:32"


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
