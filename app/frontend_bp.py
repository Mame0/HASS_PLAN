"""
Sirve el front-end HassPlan (prototipo React servido como estáticos).

- `GET /`              -> HassPlan.html (shell de la SPA)
- `GET /<archivo>`    -> assets del bundle (*.jsx, api.js, ...) desde app/frontend/

El bundle usa React UMD + Babel-in-browser, así que no hay paso de build: Flask solo
entrega los archivos. La capa de datos (`api.js`) consume la API REST bajo /api.
Las rutas de /api tienen prioridad sobre el comodín de assets (son más específicas).
"""
import os

from flask import Blueprint, send_from_directory, abort

bp = Blueprint("frontend", __name__)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")

# Solo se sirven estos tipos de archivo del bundle (evita exponer otra cosa).
EXTS_PERMITIDAS = (".html", ".js", ".jsx", ".css", ".json", ".svg", ".png", ".ico")


@bp.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "HassPlan.html")


@bp.get("/<path:filename>")
def asset(filename):
    if not filename.lower().endswith(EXTS_PERMITIDAS):
        abort(404)
    destino = os.path.join(FRONTEND_DIR, filename)
    if not os.path.isfile(destino):
        abort(404)
    # .jsx como JavaScript para que Babel-in-browser lo procese sin avisos de MIME.
    mimetype = "text/babel" if filename.endswith(".jsx") else None
    return send_from_directory(FRONTEND_DIR, filename, mimetype=mimetype)
