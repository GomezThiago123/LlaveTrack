"""Tests del login (US-01), bloqueo por intentos (US-07) y recuperacion de contrasena (US-08)."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app import correo
from app.errores import ErrorNegocio
from app.modelos import Sesion, Usuario
from app.servicios import auth
from app.tipos import ahora_utc

ANA = "ana.perez@example.com"
CLAVE = "llavetrack"  # la de seed/datos.json


def usuario(sesion, email) -> Usuario:
    return sesion.scalar(select(Usuario).where(Usuario.email == email))


def login(cliente, email=ANA, clave=CLAVE):
    return cliente.post("/api/auth/login", json={"email": email, "clave": clave})


# --- Login y sesion (US-01) ---


def test_login_correcto_deja_cookie_httponly_y_yo_devuelve_el_usuario(cliente):
    res = login(cliente)
    assert res.status_code == 200
    assert res.json()["apellido"] == "Perez"
    assert res.json()["rol"] == "DOCENTE"
    cookie = res.headers["set-cookie"]
    assert "llavetrack_sesion=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie

    assert cliente.get("/api/auth/yo").json()["email"] == ANA


def test_email_sin_importar_mayusculas_ni_espacios(cliente):
    assert login(cliente, email="  Ana.Perez@Example.com ").status_code == 200


def test_clave_incorrecta_y_email_inexistente_dan_el_mismo_error(cliente):
    mal_clave = login(cliente, clave="otra-cosa")
    sin_usuario = login(cliente, email="nadie@example.com")
    assert mal_clave.status_code == sin_usuario.status_code == 401
    assert mal_clave.json() == sin_usuario.json()
    assert mal_clave.json()["error"]["codigo"] == "CREDENCIALES_INVALIDAS"


def test_usuario_inactivo_no_puede_entrar(cliente, fabrica_sesiones):
    with fabrica_sesiones() as s:
        usuario(s, ANA).activo = False
        s.commit()
    assert login(cliente).status_code == 401


def test_usuario_sin_contrasena_no_puede_entrar(cliente, fabrica_sesiones):
    """Un usuario que solo entra con Google (password_hash null)."""
    with fabrica_sesiones() as s:
        usuario(s, ANA).password_hash = None
        s.commit()
    assert login(cliente).status_code == 401


def test_sin_cookie_las_rutas_protegidas_dan_401(cliente):
    for ruta in ("/api/auth/yo", "/api/aulas", "/api/reservas/activa"):
        res = cliente.get(ruta)
        assert res.status_code == 401, ruta
        assert res.json()["error"]["codigo"] == "NO_AUTENTICADO"


def test_cookie_inventada_da_sesion_vencida(cliente):
    cliente.cookies.set("llavetrack_sesion", "token-inventado")
    res = cliente.get("/api/auth/yo")
    assert res.status_code == 401
    assert res.json()["error"]["codigo"] == "SESION_VENCIDA"


def test_logout_cierra_la_sesion(cliente):
    login(cliente)
    assert cliente.post("/api/auth/logout").status_code == 204
    assert cliente.get("/api/auth/yo").status_code == 401


def test_sesion_vence_tras_15_minutos_sin_actividad(sesion):
    ahora = ahora_utc()
    _, token = auth.login(sesion, ANA, CLAVE, ahora)
    sesion.flush()
    assert auth.usuario_de_sesion(sesion, token, ahora + timedelta(minutes=16)) is None


def test_cada_uso_renueva_la_sesion(sesion):
    ahora = ahora_utc()
    _, token = auth.login(sesion, ANA, CLAVE, ahora)
    sesion.flush()
    # Usarla cada 10 minutos la mantiene viva aunque pase mas de 15 desde el login
    assert auth.usuario_de_sesion(sesion, token, ahora + timedelta(minutes=10)) is not None
    assert auth.usuario_de_sesion(sesion, token, ahora + timedelta(minutes=20)) is not None
    assert auth.usuario_de_sesion(sesion, token, ahora + timedelta(minutes=36)) is None


def test_la_base_no_guarda_el_token_de_la_cookie(cliente, fabrica_sesiones):
    token = login(cliente).cookies["llavetrack_sesion"]
    with fabrica_sesiones() as s:
        guardado = s.scalar(select(Sesion.token_hash))
    assert guardado != token and len(guardado) == 64


# --- Bloqueo por intentos fallidos (US-07) ---


def test_cinco_intentos_fallidos_bloquean_la_cuenta(cliente):
    for _ in range(5):
        assert login(cliente, clave="mal").status_code == 401
    # Ahora ni con la contrasena correcta
    res = login(cliente)
    assert res.status_code == 429
    assert res.json()["error"]["codigo"] == "CUENTA_BLOQUEADA"
    assert "15 min" in res.json()["error"]["mensaje"]


def test_el_bloqueo_se_levanta_a_los_15_minutos(sesion):
    ahora = ahora_utc()
    for _ in range(5):
        with pytest.raises(ErrorNegocio):
            auth.login(sesion, ANA, "mal", ahora)
    with pytest.raises(ErrorNegocio) as error:
        auth.login(sesion, ANA, CLAVE, ahora + timedelta(minutes=14))
    assert error.value.codigo == "CUENTA_BLOQUEADA"
    auth.login(sesion, ANA, CLAVE, ahora + timedelta(minutes=15, seconds=1))


def test_un_login_correcto_reinicia_el_contador(sesion):
    for _ in range(4):
        with pytest.raises(ErrorNegocio):
            auth.login(sesion, ANA, "mal")
    auth.login(sesion, ANA, CLAVE)
    for _ in range(4):
        with pytest.raises(ErrorNegocio):
            auth.login(sesion, ANA, "mal")
    auth.login(sesion, ANA, CLAVE)  # no se bloqueo: los fallidos no eran seguidos


# --- Recuperacion de contrasena (US-08) ---


@pytest.fixture
def mails(monkeypatch):
    """Junta los mails que se mandarian, en lugar de mandarlos."""
    enviados = []
    monkeypatch.setattr(correo, "enviar_correo", lambda *args: enviados.append(args))
    return enviados


def token_del_mail(mail) -> str:
    _destino, _asunto, cuerpo = mail
    return cuerpo.split("token=")[1].split()[0]


def test_recuperar_manda_link_y_permite_cambiar_la_contrasena(cliente, mails):
    res = cliente.post("/api/auth/recuperar", json={"email": ANA})
    assert res.status_code == 202
    assert len(mails) == 1 and mails[0][0] == ANA
    assert "http://localhost:5173/restablecer?token=" in mails[0][2]

    res = cliente.post(
        "/api/auth/restablecer", json={"token": token_del_mail(mails[0]), "claveNueva": "nueva-clave-123"}
    )
    assert res.status_code == 204
    assert login(cliente).status_code == 401  # la vieja ya no sirve
    assert login(cliente, clave="nueva-clave-123").status_code == 200


def test_recuperar_con_email_inexistente_responde_igual_y_no_manda_nada(cliente, mails):
    existe = cliente.post("/api/auth/recuperar", json={"email": ANA})
    no_existe = cliente.post("/api/auth/recuperar", json={"email": "nadie@example.com"})
    assert existe.status_code == no_existe.status_code == 202
    assert existe.json() == no_existe.json()
    assert len(mails) == 1


def test_el_link_sirve_una_sola_vez(cliente, mails):
    cliente.post("/api/auth/recuperar", json={"email": ANA})
    pedido = {"token": token_del_mail(mails[0]), "claveNueva": "nueva-clave-123"}
    assert cliente.post("/api/auth/restablecer", json=pedido).status_code == 204
    res = cliente.post("/api/auth/restablecer", json=pedido)
    assert res.status_code == 400
    assert res.json()["error"]["codigo"] == "LINK_INVALIDO"


def test_el_link_vence_a_los_30_minutos(sesion):
    ahora = ahora_utc()
    _, token = auth.pedir_recuperacion(sesion, ANA, ahora)
    sesion.flush()
    with pytest.raises(ErrorNegocio) as error:
        auth.restablecer_clave(sesion, token, "nueva-clave-123", ahora + timedelta(minutes=31))
    assert error.value.codigo == "LINK_INVALIDO"


def test_token_inventado_no_sirve(cliente):
    res = cliente.post("/api/auth/restablecer", json={"token": "inventado", "claveNueva": "nueva-clave-123"})
    assert res.status_code == 400


def test_contrasena_nueva_corta_se_rechaza(cliente, mails):
    cliente.post("/api/auth/recuperar", json={"email": ANA})
    res = cliente.post(
        "/api/auth/restablecer", json={"token": token_del_mail(mails[0]), "claveNueva": "corta"}
    )
    assert res.status_code == 422


def test_restablecer_desbloquea_la_cuenta_y_cierra_las_sesiones(sesion):
    _, token_sesion = auth.login(sesion, ANA, CLAVE)
    for _ in range(5):
        with pytest.raises(ErrorNegocio):
            auth.login(sesion, ANA, "mal")
    _, token = auth.pedir_recuperacion(sesion, ANA)
    sesion.flush()

    auth.restablecer_clave(sesion, token, "nueva-clave-123")

    assert auth.usuario_de_sesion(sesion, token_sesion) is None
    auth.login(sesion, ANA, "nueva-clave-123")  # ya no esta bloqueada
