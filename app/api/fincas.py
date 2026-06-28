"""
Fincas (chacra del agricultor — Módulo 2). Una finca agrupa varios lotes.

GET    /fincas          -> lista (con n_lotes)
GET    /fincas/<id>     -> finca + sus lotes
POST   /fincas          -> crea (geometría opcional -> centroide para centrar el mapa)
PUT    /fincas/<id>     -> edita
DELETE /fincas/<id>     -> elimina (cascada a sus lotes)
"""
import json

from flask import Blueprint, jsonify, request, abort

from app.models import db, Finca
from app.services import validacion as v
from app.services import geo
from app.api._common import serialize_finca

bp = Blueprint("fincas", __name__)


def _aplicar_geometria(finca, geometria):
    """Guarda el GeoJSON y deriva el centroide de la finca."""
    if geometria is None:
        return
    try:
        lat, lon = geo.centroide(geometria)
    except (ValueError, KeyError, TypeError):
        abort(400, description="Geometría GeoJSON inválida.")
    finca.geometria = json.dumps(geometria)
    finca.centro_lat = lat
    finca.centro_lon = lon


@bp.get("/fincas")
def listar():
    return jsonify([serialize_finca(f) for f in Finca.query.order_by(Finca.nombre).all()])


@bp.get("/fincas/<int:finca_id>")
def obtener(finca_id):
    f = Finca.query.get_or_404(finca_id)
    return jsonify(serialize_finca(f, con_lotes=True))


@bp.post("/fincas")
def crear():
    data = request.get_json(silent=True) or {}
    try:
        nombre = v.texto_requerido(data.get("nombre"), "nombre")
    except ValueError as e:
        abort(400, description=str(e))
    f = Finca(nombre=nombre, distrito=data.get("distrito"))
    _aplicar_geometria(f, data.get("geometria"))
    db.session.add(f)
    db.session.commit()
    return jsonify(serialize_finca(f)), 201


@bp.put("/fincas/<int:finca_id>")
def editar(finca_id):
    f = Finca.query.get_or_404(finca_id)
    data = request.get_json(silent=True) or {}
    try:
        if "nombre" in data:
            f.nombre = v.texto_requerido(data.get("nombre"), "nombre")
    except ValueError as e:
        abort(400, description=str(e))
    if "distrito" in data:
        f.distrito = data.get("distrito")
    if "geometria" in data:
        _aplicar_geometria(f, data.get("geometria"))
    db.session.commit()
    return jsonify(serialize_finca(f, con_lotes=True))


@bp.delete("/fincas/<int:finca_id>")
def eliminar(finca_id):
    f = Finca.query.get_or_404(finca_id)
    db.session.delete(f)
    db.session.commit()
    return "", 204
