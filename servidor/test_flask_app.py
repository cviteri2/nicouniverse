import base64

import pytest

import flask_app

ORIGEN = "https://nicoworld.example"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALLOWED_ORIGINS", ORIGEN)
    monkeypatch.setenv("ADMIN_PASSWORD", "clave-de-prueba")
    flask_app._visitas.clear()
    flask_app.app.config["TESTING"] = True
    return flask_app.app.test_client()


def auth():
    return {"Authorization": "Basic " + base64.b64encode(b"admin:clave-de-prueba").decode()}


def enviar(client, **kw):
    datos = {"mundo": "AstroWorld", "estrellas": 5, "alias": "Estelar", "texto": "Me encantó el 3D."}
    datos.update(kw)
    return client.post("/api/comentarios", json=datos, headers={"Origin": ORIGEN})


def test_nuevo_queda_pendiente_y_no_se_publica(client):
    r = enviar(client)
    assert r.status_code == 201 and r.json["estado"] == "pendiente"
    assert client.get("/api/comentarios").json["comentarios"] == []


def test_aprobar_lo_publica(client):
    enviar(client)
    r = client.post("/admin/1/aprobar", headers={**auth(), "Origin": "http://localhost"})
    assert r.status_code == 303
    lista = client.get("/api/comentarios").json["comentarios"]
    assert len(lista) == 1 and lista[0]["texto"] == "Me encantó el 3D."


def test_borrar(client):
    enviar(client)
    client.post("/admin/1/borrar", headers={**auth(), "Origin": "http://localhost"})
    assert "No hay comentarios" in client.get("/admin", headers=auth()).get_data(as_text=True)


@pytest.mark.parametrize("texto", ["escríbeme a nico@correo.com", "llama al 099 123 4567", "mira www.sitio.com"])
def test_bloquea_datos_de_contacto(client, texto):
    assert enviar(client, texto=texto).status_code == 400


@pytest.mark.parametrize("cambio", [{"mundo": "Otro"}, {"estrellas": 9}, {"texto": "hey"}, {"texto": "x" * 401}])
def test_valida_campos(client, cambio):
    assert enviar(client, **cambio).status_code == 400


def test_origen_no_permitido(client):
    r = client.post("/api/comentarios", json={"mundo": "AstroWorld", "estrellas": 5, "texto": "hola hola"},
                    headers={"Origin": "https://otro.com"})
    assert r.status_code == 403


def test_cors_para_el_dominio(client):
    r = client.options("/api/comentarios", headers={"Origin": ORIGEN})
    assert r.headers["Access-Control-Allow-Origin"] == ORIGEN
    r = client.get("/api/comentarios", headers={"Origin": "https://otro.com"})
    assert "Access-Control-Allow-Origin" not in r.headers


def test_limite_de_envios(client):
    codigos = [enviar(client, texto=f"comentario {i}").status_code for i in range(6)]
    assert codigos[:5] == [201] * 5 and codigos[5] == 429


def test_admin_requiere_clave(client):
    assert client.get("/admin").status_code == 401
    malo = {"Authorization": "Basic " + base64.b64encode(b"admin:mala").decode()}
    assert client.get("/admin", headers=malo).status_code == 401


def test_admin_bloquea_csrf(client):
    enviar(client)
    r = client.post("/admin/1/aprobar", headers={**auth(), "Origin": "https://malicioso.com"})
    assert r.status_code == 403


def test_admin_escapa_html(client):
    enviar(client, texto="<script>alert(1)</script>")
    pagina = client.get("/admin", headers=auth()).get_data(as_text=True)
    assert "<script>alert" not in pagina and "&lt;script&gt;" in pagina


def test_trampa_para_robots_no_guarda(client):
    assert enviar(client, web="spam").status_code == 201
    assert "No hay comentarios" in client.get("/admin", headers=auth()).get_data(as_text=True)
