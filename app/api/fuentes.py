"""M10 — Fuentes de datos: listado de proveedores meteorológicos."""
from flask import Blueprint, jsonify

from app.models import FuenteDatos
from app.api._common import serialize_fuente

bp = Blueprint("fuentes", __name__)


@bp.get("/fuentes")
def listar_fuentes():
    fuentes = FuenteDatos.query.all()
    return jsonify([serialize_fuente(f) for f in fuentes])
