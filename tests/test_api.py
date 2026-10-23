import importlib
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CAJA_DB_PATH", str(tmp_path / "caja.db"))
    monkeypatch.setenv("JWT_SECRET", "secreto-de-prueba-" + "x" * 32)
    monkeypatch.setenv("CAJA_TESORERO_USUARIO", "tesorero")
    monkeypatch.setenv("CAJA_TESORERO_CLAVE", "clave-del-tesorero")
    from app import config, main

    importlib.reload(config)
    main.INTENTOS.clear()
    with TestClient(importlib.reload(main).app) as c:
        yield c


def login(client, usuario, clave):
    r = client.post("/auth/token", data={"username": usuario, "password": clave})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def tes(client):
    return login(client, "tesorero", "clave-del-tesorero")


def nuevo_socio(client, tes, usuario="ana"):
    r = client.post("/socios", json={"nombre": "Ana Pérez", "usuario": usuario, "clave": "clave-segura-123"}, headers=tes)
    assert r.status_code == 201
    return r.json()["id"], login(client, usuario, "clave-segura-123")


def mover(client, tes, socio_id, tipo, monto, efectivo=True):
    return client.post("/movimientos", json={"socio_id": socio_id, "tipo": tipo, "monto": monto, "efectivo": efectivo}, headers=tes)


def test_sin_token_y_token_falso(client):
    assert client.get("/socios").status_code == 401
    assert client.get("/socios", headers={"Authorization": "Bearer falso"}).status_code == 401


def test_clave_incorrecta_y_limite_de_intentos(client):
    codes = [client.post("/auth/token", data={"username": "tesorero", "password": "mala"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_socio_no_puede_hacer_operaciones_de_tesorero(client, tes):
    socio_id, ana = nuevo_socio(client, tes)
    assert mover(client, ana, socio_id, "deposito", "10").status_code == 403
    assert client.get("/socios", headers=ana).status_code == 403


def test_ahorro_aporte_y_retiro(client, tes):
    socio_id, ana = nuevo_socio(client, tes)
    assert mover(client, tes, socio_id, "deposito", "150.50").json()["saldo_ahorro"] == "150.50"
    mover(client, tes, socio_id, "aporte", "5")
    assert mover(client, tes, socio_id, "retiro", "200").status_code == 409
    assert mover(client, tes, socio_id, "retiro", "50.50").json()["saldo_ahorro"] == "100.00"
    estado = client.get("/socios/yo", headers=ana).json()
    assert estado["ahorro"] == "100.00" and estado["aportes"] == "5.00"


def test_alertas_uafe_y_fraccionamiento(client, tes):
    socio_id, _ = nuevo_socio(client, tes)
    assert mover(client, tes, socio_id, "deposito", "10000").json()["alertas"] == ["uafe_efectivo"]
    socio2, _ = nuevo_socio(client, tes, "beto")
    mover(client, tes, socio2, "deposito", "6000")
    assert mover(client, tes, socio2, "deposito", "4500").json()["alertas"] == ["fraccionamiento"]
    assert mover(client, tes, socio2, "deposito", "4500", efectivo=False).json()["alertas"] == []
    assert len(client.get("/alertas", headers=tes).json()) == 2


def test_prestamo_rechazado_por_encaje(client, tes):
    socio_id, ana = nuevo_socio(client, tes)
    mover(client, tes, socio_id, "deposito", "100")
    pid = client.post("/prestamos", json={"monto": "1000", "plazo_meses": 12, "tasa_anual": 0.15}, headers=ana).json()["id"]
    assert client.post(f"/prestamos/{pid}/aprobar", headers=tes).json()["estado"] == "rechazado"


def test_prestamo_completo_con_mora(client, tes, monkeypatch):
    socio_id, ana = nuevo_socio(client, tes)
    mover(client, tes, socio_id, "deposito", "400")
    sim = client.post("/prestamos/simular", json={"monto": "1000", "plazo_meses": 12, "tasa_anual": 0.15}, headers=ana).json()
    assert sim["cuotas"][0]["cuota"] == "90.26"
    pid = client.post("/prestamos", json={"monto": "1000", "plazo_meses": 12, "tasa_anual": 0.15}, headers=ana).json()["id"]
    assert client.post(f"/prestamos/{pid}/aprobar", headers=tes).json()["estado"] == "aprobado"
    assert client.get("/socios/yo", headers=ana).json()["ahorro"] == "1400.00"  # el desembolso va al ahorro

    # 36 días después del primer vencimiento la cuota tiene mora
    from app import main

    class Futuro(date):
        @classmethod
        def today(cls):
            return date.today() + timedelta(days=67)

    monkeypatch.setattr(main, "date", Futuro)
    cuota = client.get(f"/prestamos/{pid}", headers=ana).json()["cuotas"][0]
    assert cuota["dias_atraso"] > 30 and cuota["mora"] != "0.00"
    pago = client.post(f"/prestamos/{pid}/pagar", headers=tes).json()
    assert pago["cuota"] == 1 and float(pago["cobrado"]) > 90.26
    rep = client.get("/reportes/cartera", headers=tes).json()
    assert float(rep["morosidad"]) > 0


def test_socio_no_ve_prestamos_ajenos(client, tes):
    socio_id, ana = nuevo_socio(client, tes)
    _, beto = nuevo_socio(client, tes, "beto")
    pid = client.post("/prestamos", json={"monto": "100", "plazo_meses": 3, "tasa_anual": 0.1}, headers=ana).json()["id"]
    assert client.get(f"/prestamos/{pid}", headers=beto).status_code == 404


def test_metricas_y_cabeceras(client):
    r = client.get("/salud")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "caja_http_requests_total" in client.get("/metrics").text
