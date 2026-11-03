"""Lo que se usa al correr en la nube: la web compilada, el mail por Brevo y MQTT con TLS."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import correo, mqtt_cliente
from app.config import config
from app.main import montar_web


def web_de_prueba(tmp_path) -> TestClient:
    """Una app con una ruta de la API y una web compilada de mentira."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>LlaveTrack</html>")
    (dist / "assets" / "app.js").write_text("console.log('hola')")
    (tmp_path / "secreto.txt").write_text("no se tiene que ver")

    app = FastAPI()

    @app.get("/api/salud")
    def salud():
        return {"ok": True}

    montar_web(app, dist)
    return TestClient(app)


def test_la_web_compilada_se_entrega_desde_el_servidor(tmp_path):
    cliente = web_de_prueba(tmp_path)
    assert cliente.get("/").text == "<html>LlaveTrack</html>"
    assert cliente.get("/assets/app.js").text == "console.log('hola')"
    # Las direcciones de React (ej. /aulas) devuelven index.html: las resuelve la web
    assert cliente.get("/aulas").text == "<html>LlaveTrack</html>"
    # La API sigue andando
    assert cliente.get("/api/salud").json() == {"ok": True}


def test_una_ruta_de_la_api_que_no_existe_es_404_y_no_la_web(tmp_path):
    cliente = web_de_prueba(tmp_path)
    assert cliente.get("/api/no-existe").status_code == 404


def test_no_se_puede_salir_de_la_carpeta_de_la_web(tmp_path):
    cliente = web_de_prueba(tmp_path)
    res = cliente.get("/..%2Fsecreto.txt")
    assert "no se tiene que ver" not in res.text


def test_con_brevo_el_mail_sale_por_su_api(monkeypatch):
    pedidos = []

    class Respuesta:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def urlopen_falso(pedido, timeout):
        pedidos.append(pedido)
        return Respuesta()

    monkeypatch.setattr(config, "brevo_api_key", "clave-de-prueba")
    monkeypatch.setattr(config, "brevo_remitente", "llavetrack@example.com")
    monkeypatch.setattr(correo.urllib.request, "urlopen", urlopen_falso)

    correo.enviar_correo("ana@example.com", "Asunto", "Cuerpo")

    assert len(pedidos) == 1
    pedido = pedidos[0]
    assert pedido.full_url == correo.BREVO_URL
    assert pedido.get_header("Api-key") == "clave-de-prueba"
    datos = json.loads(pedido.data)
    assert datos["to"] == [{"email": "ana@example.com"}]
    assert datos["sender"]["email"] == "llavetrack@example.com"
    assert datos["subject"] == "Asunto"
    assert datos["textContent"] == "Cuerpo"


def test_mqtt_con_tls_activa_el_cifrado(monkeypatch, fabrica_sesiones):
    llamadas = []
    monkeypatch.setattr(config, "mqtt_tls", True)
    monkeypatch.setattr(mqtt_cliente.mqtt.Client, "tls_set", lambda self, *a, **k: llamadas.append(a))
    mqtt_cliente.ClienteMqtt(fabrica_sesiones)
    assert len(llamadas) == 1


def test_mqtt_sin_tls_no_lo_activa(monkeypatch, fabrica_sesiones):
    llamadas = []
    monkeypatch.setattr(mqtt_cliente.mqtt.Client, "tls_set", lambda self, *a, **k: llamadas.append(a))
    mqtt_cliente.ClienteMqtt(fabrica_sesiones)
    assert llamadas == []
