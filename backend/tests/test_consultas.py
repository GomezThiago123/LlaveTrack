"""Las listas no hacen una consulta por cada fila.

Con SQLite no se nota, pero con Supabase cada consulta tarda ~170 ms desde Argentina:
/api/aulas llego a hacer 35 (6,7 s) porque pedia el aula de cada llave por separado.
"""

import pytest
from sqlalchemy import event

LIMITE = 10  # consultas por pedido, con 5 aulas o con 30


@pytest.fixture
def contar_consultas(fabrica_sesiones):
    engine = fabrica_sesiones.kw["bind"]
    consultas = []

    def anotar(*_args):
        consultas.append(1)

    event.listen(engine, "before_cursor_execute", anotar)
    yield consultas
    event.remove(engine, "before_cursor_execute", anotar)


@pytest.mark.parametrize(
    "ruta",
    ["/api/publico/estado", "/api/aulas", "/api/equipo", "/api/prestamos", "/api/prestamos/mios", "/api/incidentes"],
)
def test_las_listas_hacen_pocas_consultas(cliente, ingresar, contar_consultas, ruta):
    ingresar("carla.diaz@example.com")
    contar_consultas.clear()
    assert cliente.get(ruta).status_code == 200
    assert len(contar_consultas) <= LIMITE, f"{ruta} hizo {len(contar_consultas)} consultas"
