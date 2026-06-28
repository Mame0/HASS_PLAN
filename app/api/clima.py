"""
Sincronización climática (motor de variables automáticas por API).

POST /lotes/<id>/clima/sync   -> dispara el fetch + derivación, llena las 12 climáticas
GET  /clima/log               -> log de sincronizaciones (M10)
"""
from flask import Blueprint, jsonify, request, abort

from app.models import Lote, ClimaSync
from app.services.clima.sync import sincronizar_clima
from app.api._common import (
    get_campana, bloquear_si_cerrada, get_or_create_registro, serialize_variables, serialize_clima_sync,
    validar_lote_en_campana,
)

bp = Blueprint("clima", __name__)


@bp.post("/lotes/<int:lote_id>/clima/sync")
def sync_lote(lote_id):
    lote = Lote.query.get_or_404(lote_id)
    campana = get_campana(request.args.get("campana_id", type=int))
    if campana is None:
        abort(404, description="No hay campaña disponible.")
    validar_lote_en_campana(lote, campana)
    bloquear_si_cerrada(campana)
    if campana.fecha_inicio is None or campana.fecha_fin is None:
        abort(400, description="La campaña no tiene ventana de fechas definida.")

    registro = get_or_create_registro(lote, campana)
    cs = sincronizar_clima(registro, lote, campana)

    resp = {
        "sync": serialize_clima_sync(cs),
        "variables": serialize_variables(lote, campana),
    }
    return jsonify(resp), (200 if cs.status == "ok" else 502)


@bp.get("/clima/log")
def clima_log():
    q = ClimaSync.query
    lote_id = request.args.get("lote_id", type=int)
    if lote_id:
        q = q.filter_by(lote_id=lote_id)
    limit = request.args.get("limit", default=50, type=int)
    filas = q.order_by(ClimaSync.fetched_at.desc()).limit(limit).all()
    return jsonify([serialize_clima_sync(cs) for cs in filas])
