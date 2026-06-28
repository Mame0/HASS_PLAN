"""
Planificación de cosecha (Módulo 5 / F4).

POST /campanas/<id>/plan-cosecha  -> genera la distribución semanal desde el total predicho
GET  /campanas/<id>/plan-cosecha  -> lee el plan + sus semanas
PUT  /semanas/<id>                -> reprograma una semana (redistribuye el resto)
PUT  /semanas/<id>/real           -> registra la cosecha real de una semana (F7)
"""
from flask import Blueprint, jsonify, request, abort

from app.models import SemanaCosecha
from app.services import validacion as v
from app.services.planificacion import (generar_plan_cosecha, reprogramar_semana,
                                        registrar_cosecha_real)
from app.api._common import get_campana_o_404, bloquear_si_cerrada, serialize_plan_cosecha

bp = Blueprint("cosecha", __name__)


@bp.post("/campanas/<int:campana_id>/plan-cosecha")
def generar(campana_id):
    campana = get_campana_o_404(campana_id)
    bloquear_si_cerrada(campana)
    data = request.get_json(silent=True) or {}
    try:
        fecha_inicio = v.fecha(data.get("fecha_inicio"), "fecha_inicio")
        semanas_total = v.entero_no_negativo(data.get("semanas_total"), "semanas_total",
                                             permitir_none=False)
        curva = (data.get("curva") or "campana").strip().lower()
        plan = generar_plan_cosecha(campana, fecha_inicio, semanas_total, curva)
    except ValueError as e:
        abort(400, description=str(e))
    return jsonify(serialize_plan_cosecha(plan)), 201


@bp.get("/campanas/<int:campana_id>/plan-cosecha")
def obtener(campana_id):
    campana = get_campana_o_404(campana_id)
    if campana.plan_cosecha is None:
        abort(404, description="La campaña aún no tiene plan de cosecha.")
    return jsonify(serialize_plan_cosecha(campana.plan_cosecha))


@bp.put("/semanas/<int:semana_id>")
def reprogramar(semana_id):
    semana = SemanaCosecha.query.get_or_404(semana_id)
    bloquear_si_cerrada(semana.plan.campana)
    data = request.get_json(silent=True) or {}
    if "tn_planificada" not in data:
        abort(400, description="Falta 'tn_planificada'.")
    try:
        nuevo = float(data["tn_planificada"])
    except (ValueError, TypeError):
        abort(400, description="'tn_planificada' debe ser numérico.")
    try:
        plan = reprogramar_semana(semana, nuevo)
    except ValueError as e:
        abort(400, description=str(e))
    return jsonify(serialize_plan_cosecha(plan))


@bp.put("/semanas/<int:semana_id>/real")
def registrar_real(semana_id):
    semana = SemanaCosecha.query.get_or_404(semana_id)
    bloquear_si_cerrada(semana.plan.campana)
    data = request.get_json(silent=True) or {}
    if "tn_real" not in data:
        abort(400, description="Falta 'tn_real'.")
    bruto = data["tn_real"]
    if bruto is None or bruto == "":
        nuevo = None                       # borra el registro de cosecha real
    else:
        try:
            nuevo = float(bruto)
        except (ValueError, TypeError):
            abort(400, description="'tn_real' debe ser numérico o nulo.")
    try:
        plan = registrar_cosecha_real(semana, nuevo)
    except ValueError as e:
        abort(400, description=str(e))
    return jsonify(serialize_plan_cosecha(plan))
