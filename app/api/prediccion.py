"""
Predicción de rendimiento (Módulo 4: Inteligencia Agrícola).

POST /lotes/<id>/prediccion        -> predice, persiste y devuelve tn_ha/total + bandera OOD
GET  /lotes/<id>/prediccion        -> relee la última predicción del lote
GET  /campanas/<id>/prediccion     -> total de campaña (Σ tn_total por lote)
"""
from flask import Blueprint, jsonify, request, abort

from app.models import Lote, Prediccion
from app.services.prediccion import predecir_lote, total_campana
from app.api._common import (
    get_campana, bloquear_si_cerrada, serialize_prediccion, validar_lote_en_campana,
)

bp = Blueprint("prediccion", __name__)


def _campana_o_404():
    campana = get_campana(request.args.get("campana_id", type=int))
    if campana is None:
        abort(404, description="No hay campaña disponible.")
    return campana


@bp.post("/lotes/<int:lote_id>/prediccion")
def predecir(lote_id):
    lote = Lote.query.get_or_404(lote_id)
    campana = _campana_o_404()
    validar_lote_en_campana(lote, campana)
    bloquear_si_cerrada(campana)
    try:
        pred, res = predecir_lote(lote, campana)
    except ValueError as e:
        abort(400, description=str(e))
    except FileNotFoundError as e:
        abort(503, description=str(e))
    return jsonify(serialize_prediccion(pred, res))


@bp.get("/lotes/<int:lote_id>/prediccion")
def leer(lote_id):
    lote = Lote.query.get_or_404(lote_id)
    campana = _campana_o_404()
    validar_lote_en_campana(lote, campana)
    pred = Prediccion.query.filter_by(lote_id=lote_id, campana_id=campana.id).first()
    if pred is None:
        abort(404, description="El lote aún no tiene predicción en esta campaña.")
    return jsonify(serialize_prediccion(pred))


@bp.get("/campanas/<int:campana_id>/prediccion")
def total(campana_id):
    campana = get_campana(campana_id)
    if campana is None:
        abort(404, description="Campaña no encontrada.")
    return jsonify(total_campana(campana))
