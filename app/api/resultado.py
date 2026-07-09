"""
Resultado de cosecha (F7 — cierre y validación del modelo).

Carga la cosecha REAL por lote y la compara contra la predicción (predicho vs real).

  GET    /campanas/<id>/resultados             -> comparación por lote + métricas (MAE/MAPE)
  PUT    /lotes/<lote_id>/resultado?campana_id  -> upsert de la cosecha real del lote
  DELETE /lotes/<lote_id>/resultado?campana_id  -> borra la cosecha real del lote
"""
from flask import Blueprint, jsonify, request, abort

from app.models import Lote
from app.services import resultado as svc
from app.api._common import (
    get_campana, get_campana_o_404, bloquear_si_cerrada, validar_lote_en_campana,
)

bp = Blueprint("resultado", __name__)


def _campana_o_404():
    campana = get_campana(request.args.get("campana_id", type=int))
    if campana is None:
        abort(404, description="No hay campaña disponible.")
    return campana


@bp.get("/campanas/<int:campana_id>/resultados")
def comparacion(campana_id):
    campana = get_campana_o_404(campana_id)
    return jsonify(svc.comparacion_campana(campana))


@bp.put("/lotes/<int:lote_id>/resultado")
def guardar(lote_id):
    lote = Lote.query.get_or_404(lote_id)
    campana = _campana_o_404()
    validar_lote_en_campana(lote, campana)
    bloquear_si_cerrada(campana)
    data = request.get_json(silent=True) or {}
    try:
        rc = svc.guardar_resultado(
            lote, campana,
            tn_ha_real=data.get("tn_ha_real"),
            frutos_arbol=data.get("frutos_arbol"),
            peso_fruto=data.get("peso_fruto"),
            fecha_cierre=data.get("fecha_cierre"),
        )
    except ValueError as e:
        abort(400, description=str(e))
    return jsonify(svc.serialize_resultado(rc))


@bp.delete("/lotes/<int:lote_id>/resultado")
def borrar(lote_id):
    lote = Lote.query.get_or_404(lote_id)
    campana = _campana_o_404()
    validar_lote_en_campana(lote, campana)
    bloquear_si_cerrada(campana)
    svc.borrar_resultado(lote, campana)
    return jsonify(ok=True)
