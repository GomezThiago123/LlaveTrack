"""Errores de negocio y formato comun de errores de la API.

Todas las respuestas de error tienen la forma:
    {"error": {"codigo": "LLAVE_NO_DISPONIBLE", "mensaje": "..."}}
El codigo es para el programa (la web decide que hacer); el mensaje es para mostrar.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorNegocio(Exception):
    """Una regla del sistema impide hacer lo que se pidio (ej. la llave ya esta reservada)."""

    def __init__(self, status: int, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.status = status
        self.codigo = codigo
        self.mensaje = mensaje


def respuesta_error(status: int, codigo: str, mensaje: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"codigo": codigo, "mensaje": mensaje}})


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorNegocio)
    def _error_negocio(_request: Request, error: ErrorNegocio):
        return respuesta_error(error.status, error.codigo, error.mensaje)

    @app.exception_handler(RequestValidationError)
    def _datos_invalidos(_request: Request, error: RequestValidationError):
        detalle = "; ".join(
            f"{'.'.join(str(parte) for parte in e['loc'])}: {e['msg']}" for e in error.errors()
        )
        return respuesta_error(422, "DATOS_INVALIDOS", f"Datos inválidos ({detalle})")
