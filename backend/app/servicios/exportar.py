"""US-19: el historial de prestamos en un archivo de Excel (.xlsx), con openpyxl.

Las mismas columnas que se ven en la web (Historial). Las fechas van en hora de Argentina:
Excel no sabe de zonas horarias.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font

from app.modelos import Prestamo
from app.tipos import ZONA_ARGENTINA

COLUMNAS = ["Aula", "Docente", "Email", "Retiro", "Devolución", "Duración", "Estado"]
FORMATO_FECHA = "dd/mm/yyyy hh:mm"


def _hora_argentina(fecha):
    # Excel guarda fechas sin zona: se pasa a hora de Argentina y se le saca la zona
    return fecha.astimezone(ZONA_ARGENTINA).replace(tzinfo=None) if fecha else None


def _duracion(prestamo: Prestamo) -> str:
    """Como en la web: "1h 05m" o "45m"."""
    if prestamo.devuelto_en is None:
        return ""
    minutos = int((prestamo.devuelto_en - prestamo.retirado_en).total_seconds() // 60)
    horas = minutos // 60
    return f"{horas}h {minutos % 60:02d}m" if horas else f"{minutos}m"


def _estado(prestamo: Prestamo) -> str:
    if prestamo.devuelto_en is None:
        return "Sin devolver"
    return "Perdida" if prestamo.perdida else "Devuelta"


def historial_xlsx(prestamos: list[Prestamo]) -> bytes:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Historial"
    hoja.append(COLUMNAS)
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    for p in prestamos:
        u = p.usuario
        hoja.append(
            [
                p.llave.aula.nombre,
                f"{u.nombre} {u.apellido}",
                u.email,
                _hora_argentina(p.retirado_en),
                _hora_argentina(p.devuelto_en),
                _duracion(p),
                _estado(p),
            ]
        )
    for fila in hoja.iter_rows(min_row=2, min_col=4, max_col=5):
        for celda in fila:
            celda.number_format = FORMATO_FECHA
    for letra, ancho in zip("ABCDEFG", [12, 24, 30, 17, 17, 10, 13]):
        hoja.column_dimensions[letra].width = ancho
    hoja.freeze_panes = "A2"  # el encabezado queda fijo al bajar
    hoja.auto_filter.ref = hoja.dimensions  # filtros de Excel en cada columna

    archivo = BytesIO()
    libro.save(archivo)
    return archivo.getvalue()
