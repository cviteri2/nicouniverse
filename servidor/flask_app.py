"""Nico World: servidor de comentarios para PythonAnywhere (plan gratuito).

La página (index.html) se publica en GitHub Pages con el dominio propio.
Este servidor solo guarda y entrega las opiniones:

  GET  /api/comentarios        Comentarios aprobados (los más nuevos primero).
  POST /api/comentarios        Recibe un comentario; queda pendiente de revisión.
  GET  /admin                  Panel privado para aprobar o borrar (usuario y contraseña).
  POST /webhook/github         Despliegue automático, igual que AstroWorld.

Variables de entorno (se definen en el archivo WSGI de PythonAnywhere):
  ADMIN_PASSWORD         Contraseña del panel. Sin ella, /admin responde 404.
  ADMIN_USER             Usuario del panel (por defecto, admin).
  ALLOWED_ORIGINS        Dominios que pueden usar la API, separados por comas
                         (ej.: https://tudominio.com,https://www.tudominio.com).
  DATA_DIR               Carpeta de la base de datos (por defecto, servidor/data).
  GITHUB_WEBHOOK_SECRET, DEPLOY_BRANCH, WSGI_FILE   Igual que en AstroWorld.

Privacidad: no se guarda la IP. Para frenar el spam se usa un resumen (hash)
de la IP con una sal que cambia cada día, y solo en memoria.
"""
import hashlib
import hmac
import html
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Flask, Response, abort, g, jsonify, redirect, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MUNDOS = {"Nico World", "AstroWorld", "FlagWorld", "Humanity World"}
MAX_ALIAS = 24
MAX_TEXTO = 400
MIN_TEXTO = 5
MAX_PENDIENTES = 300          # si hay más sin revisar, se rechazan nuevos (evita inundaciones)
LIMITE_VENTANA = (5, 10 * 60) # 5 comentarios cada 10 minutos por visitante
LIMITE_DIA = 20               # y 20 por día

# Los mismos filtros que la página: correos, teléfonos y enlaces.
PROHIBIDO = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    re.compile(r"(\+?\d[\s-]?){7,}"),
    re.compile(r"(https?://|www\.)", re.I),
]

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024


# --- Base de datos -------------------------------------------------------

def _db_path():
    data_dir = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "comentarios.db")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(_db_path())
        g.db.row_factory = sqlite3.Row
        g.db.execute(
            """CREATE TABLE IF NOT EXISTS comentarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mundo TEXT NOT NULL,
                estrellas INTEGER NOT NULL,
                alias TEXT NOT NULL DEFAULT '',
                texto TEXT NOT NULL,
                fecha TEXT NOT NULL,
                aprobado INTEGER NOT NULL DEFAULT 0
            )"""
        )
    return g.db


@app.teardown_appcontext
def _close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# --- Cabeceras y CORS ----------------------------------------------------

def _allowed_origins():
    return {o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()}


@app.after_request
def headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.path.startswith("/api/"):
        origin = request.headers.get("Origin", "").rstrip("/")
        if origin and origin in _allowed_origins():
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Max-Age"] = "86400"
            response.headers["Vary"] = "Origin"
    if request.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
    return response


@app.route("/")
def index():
    return jsonify(servicio="Nico World · comentarios", estado="ok")


# --- API -----------------------------------------------------------------

def _tiene_datos(s):
    return any(p.search(s) for p in PROHIBIDO)


_visitas = defaultdict(deque)


def _visitante():
    # PythonAnywhere pone la IP real en X-Real-IP.
    ip = request.headers.get("X-Real-IP") or request.remote_addr or ""
    sal = datetime.now(timezone.utc).strftime("%Y-%m-%d") + app.config.setdefault("SAL", secrets.token_hex(16))
    return hashlib.sha256((sal + ip).encode()).hexdigest()


def _limite_superado():
    ahora = time.time()
    marcas = _visitas[_visitante()]
    while marcas and ahora - marcas[0] > 86400:
        marcas.popleft()
    n_ventana, segundos = LIMITE_VENTANA
    recientes = sum(1 for t in marcas if ahora - t < segundos)
    if recientes >= n_ventana or len(marcas) >= LIMITE_DIA:
        return True
    marcas.append(ahora)
    return False


@app.route("/api/comentarios", methods=["OPTIONS"])
def comentarios_preflight():
    return ("", 204)


@app.route("/api/comentarios", methods=["GET"])
def comentarios_lista():
    filas = db().execute(
        "SELECT mundo, estrellas, alias, texto, fecha FROM comentarios "
        "WHERE aprobado = 1 ORDER BY id DESC LIMIT 200"
    ).fetchall()
    response = jsonify(comentarios=[dict(f) for f in filas])
    response.headers["Cache-Control"] = "public, max-age=60"
    return response


@app.route("/api/comentarios", methods=["POST"])
def comentarios_nuevo():
    origin = request.headers.get("Origin", "").rstrip("/")
    allowed = _allowed_origins()
    if allowed and origin not in allowed:
        return jsonify(error="origen no permitido"), 403

    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        return jsonify(error="datos inválidos"), 400
    if d.get("web"):  # campo trampa
        return jsonify(ok=True), 201

    mundo = str(d.get("mundo", "")).strip()
    alias = " ".join(str(d.get("alias", "")).split())[:MAX_ALIAS]
    texto = str(d.get("texto", "")).strip()
    try:
        estrellas = int(d.get("estrellas", 0))
    except (TypeError, ValueError):
        estrellas = 0

    if mundo not in MUNDOS:
        return jsonify(error="mundo inválido"), 400
    if not 1 <= estrellas <= 5:
        return jsonify(error="calificación inválida"), 400
    if not MIN_TEXTO <= len(texto) <= MAX_TEXTO:
        return jsonify(error="el comentario debe tener entre 5 y 400 caracteres"), 400
    if _tiene_datos(texto) or _tiene_datos(alias):
        return jsonify(error="no incluyas correos, teléfonos ni enlaces"), 400
    if _limite_superado():
        return jsonify(error="demasiados comentarios; inténtalo más tarde"), 429

    conn = db()
    pendientes = conn.execute("SELECT COUNT(*) FROM comentarios WHERE aprobado = 0").fetchone()[0]
    if pendientes >= MAX_PENDIENTES:
        return jsonify(error="no se pueden recibir comentarios ahora"), 503

    fecha = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn.execute(
        "INSERT INTO comentarios (mundo, estrellas, alias, texto, fecha) VALUES (?, ?, ?, ?, ?)",
        (mundo, estrellas, alias, texto, fecha),
    )
    conn.commit()
    return jsonify(ok=True, estado="pendiente"), 201


# --- Panel de revisión ---------------------------------------------------

def _admin_ok():
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        abort(404)
    auth = request.authorization
    user = os.environ.get("ADMIN_USER", "admin")
    return bool(
        auth
        and hmac.compare_digest(auth.username or "", user)
        and hmac.compare_digest(auth.password or "", password)
    )


def _pedir_login():
    return Response("Acceso restringido", 401, {"WWW-Authenticate": 'Basic realm="Nico World", charset="UTF-8"'})


def _mismo_sitio():
    # Bloquea formularios enviados desde otros sitios (CSRF).
    fuente = request.headers.get("Origin") or request.headers.get("Referer") or ""
    return urlparse(fuente).netloc == request.host


ADMIN_HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Nico World · Revisión</title>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#07112b;color:#eef5ff}}
main{{width:min(900px,100% - 32px);margin:32px auto}}
h1{{margin:0 0 4px}} h2{{margin:32px 0 12px;font-size:1.2rem;color:#5fd3ff}}
p.sub{{color:#a6badb;margin:0}}
.c{{border:1px solid rgba(140,190,255,.2);border-radius:12px;padding:14px 16px;margin-bottom:10px;background:rgba(120,180,255,.05)}}
.m{{font-size:.85rem;color:#a6badb;margin-bottom:6px}} .t{{white-space:pre-wrap;overflow-wrap:anywhere}}
form{{display:inline}} button{{font:inherit;border:0;border-radius:8px;padding:6px 14px;cursor:pointer;margin:8px 6px 0 0}}
.ok{{background:#5fd3ff;color:#04162e}} .no{{background:transparent;color:#ff6fb5;border:1px solid #ff6fb5}}
.vacio{{color:#a6badb}}
</style></head><body><main>
<h1>Revisión de comentarios</h1><p class="sub">{n_pend} pendientes · {n_apr} publicados</p>
<h2>Pendientes</h2>{pendientes}
<h2>Publicados (últimos 50)</h2>{aprobados}
</main></body></html>"""


def _tarjeta(f, pendiente):
    botones = ""
    if pendiente:
        botones += f'<form method="post" action="/admin/{f["id"]}/aprobar"><button class="ok">Aprobar</button></form>'
    botones += f'<form method="post" action="/admin/{f["id"]}/borrar"><button class="no">Borrar</button></form>'
    return (
        '<div class="c"><div class="m">'
        f'{html.escape(f["alias"] or "Jugador anónimo")} · {html.escape(f["mundo"])} · '
        f'{"★" * f["estrellas"]} · {html.escape(f["fecha"][:16].replace("T", " "))} UTC</div>'
        f'<div class="t">{html.escape(f["texto"])}</div>{botones}</div>'
    )


@app.route("/admin")
def admin():
    if not _admin_ok():
        return _pedir_login()
    conn = db()
    pend = conn.execute("SELECT * FROM comentarios WHERE aprobado = 0 ORDER BY id").fetchall()
    apr = conn.execute("SELECT * FROM comentarios WHERE aprobado = 1 ORDER BY id DESC LIMIT 50").fetchall()
    n_apr = conn.execute("SELECT COUNT(*) FROM comentarios WHERE aprobado = 1").fetchone()[0]
    vacio = '<p class="vacio">No hay comentarios.</p>'
    return ADMIN_HTML.format(
        n_pend=len(pend), n_apr=n_apr,
        pendientes="".join(_tarjeta(f, True) for f in pend) or vacio,
        aprobados="".join(_tarjeta(f, False) for f in apr) or vacio,
    )


@app.route("/admin/<int:cid>/<accion>", methods=["POST"])
def admin_accion(cid, accion):
    if not _admin_ok():
        return _pedir_login()
    if not _mismo_sitio():
        abort(403)
    conn = db()
    if accion == "aprobar":
        conn.execute("UPDATE comentarios SET aprobado = 1 WHERE id = ?", (cid,))
    elif accion == "borrar":
        conn.execute("DELETE FROM comentarios WHERE id = ?", (cid,))
    else:
        abort(404)
    conn.commit()
    return redirect("/admin", code=303)


# --- Despliegue automático desde GitHub (igual que AstroWorld) -----------

def _valid_signature(secret, body, header):
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def _reload_app():
    wsgi_file = os.environ.get("WSGI_FILE")
    if wsgi_file and os.path.isfile(wsgi_file):
        os.utime(wsgi_file, None)


@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        abort(404)
    if not _valid_signature(secret, request.get_data(), request.headers.get("X-Hub-Signature-256")):
        abort(403)

    event = request.headers.get("X-GitHub-Event")
    if event == "ping":
        return jsonify(status="pong")
    if event != "push":
        return jsonify(status="ignored", reason="evento no es push"), 202

    payload = request.get_json(silent=True) or {}
    branch = os.environ.get("DEPLOY_BRANCH", "main")
    if payload.get("ref") != "refs/heads/" + branch:
        return jsonify(status="ignored", reason="otra rama"), 202

    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only", "origin", branch],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=20,
        )
    except subprocess.TimeoutExpired:
        print("webhook: git pull excedió el tiempo", file=sys.stderr)
        return jsonify(status="error", reason="timeout"), 500
    if result.returncode != 0:
        print("webhook: git pull falló\n" + result.stderr, file=sys.stderr)
        return jsonify(status="error", reason="git pull falló"), 500

    response = jsonify(status="deployed")
    response.call_on_close(_reload_app)
    return response


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5001)))
