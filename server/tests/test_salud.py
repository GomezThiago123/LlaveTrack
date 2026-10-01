from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_salud_responde_ok():
    res = cliente.get("/api/salud")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
