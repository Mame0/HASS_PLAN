"""
Módulos derivados de la cosecha (Fase F5): Mano de Obra (M6), Logística (M7), Transporte (M8).
Todos consumen el Plan de Cosecha (F4) de la campaña.

PUT /campanas/<id>/mano-obra   -> configura rendimiento/cuadrillas y calcula jornales por semana
GET /campanas/<id>/mano-obra
PUT /campanas/<id>/transporte  -> configura flota/capacidad y calcula camiones/viajes/costo
GET /campanas/<id>/transporte
PUT /campanas/<id>/inventario  -> fija los materiales disponibles (recalcula logística)
GET /campanas/<id>/inventario
GET /campanas/<id>/logistica   -> requerimiento de materiales por semana (pico vs stock)
"""
from flask import Blueprint, jsonify, request, abort

from app.services import derivados
from app.api._common import (
    get_campana_o_404, bloquear_si_cerrada, serialize_mano_obra, serialize_transporte,
    serialize_inventario, serialize_logistica,
)

bp = Blueprint("derivados", __name__)


def _num(valor, campo):
    if valor is None:
        return None
    try:
        return float(valor)
    except (ValueError, TypeError):
        raise ValueError(f"'{campo}' debe ser numérico.")


def _int(valor, campo):
    if valor is None:
        return None
    try:
        return int(valor)
    except (ValueError, TypeError):
        raise ValueError(f"'{campo}' debe ser un entero.")


def _plan_o_400(campana_id):
    """Campaña + su plan de cosecha; 400 si aún no se generó (F4 es prerrequisito)."""
    campana = get_campana_o_404(campana_id)
    if campana.plan_cosecha is None:
        abort(400, description="La campaña no tiene plan de cosecha; genéralo primero (F4).")
    return campana, campana.plan_cosecha


# --------------------------- M6 Mano de obra ---------------------------

@bp.put("/campanas/<int:campana_id>/mano-obra")
def set_mano_obra(campana_id):
    bloquear_si_cerrada(get_campana_o_404(campana_id))
    _, plan = _plan_o_400(campana_id)
    data = request.get_json(silent=True) or {}
    try:
        pmo = derivados.configurar_mano_obra(
            plan,
            rendimiento_jornal=_num(data.get("rendimiento_jornal"), "rendimiento_jornal"),
            tam_cuadrilla=_int(data.get("tam_cuadrilla"), "tam_cuadrilla"),
            cuadrillas_disponibles=_int(data.get("cuadrillas_disponibles", 0), "cuadrillas_disponibles"),
            dias_cosecha_semana=_int(data.get("dias_cosecha_semana", 6), "dias_cosecha_semana"))
    except ValueError as e:
        abort(400, description=str(e))
    return jsonify(serialize_mano_obra(pmo))


@bp.get("/campanas/<int:campana_id>/mano-obra")
def get_mano_obra(campana_id):
    _, plan = _plan_o_400(campana_id)
    if plan.plan_mano_obra is None:
        abort(404, description="La campaña aún no tiene plan de mano de obra.")
    return jsonify(serialize_mano_obra(plan.plan_mano_obra))


# --------------------------- M8 Transporte ---------------------------

@bp.put("/campanas/<int:campana_id>/transporte")
def set_transporte(campana_id):
    bloquear_si_cerrada(get_campana_o_404(campana_id))
    _, plan = _plan_o_400(campana_id)
    data = request.get_json(silent=True) or {}
    try:
        pt = derivados.configurar_transporte(
            plan,
            cap_camion_tn=_num(data.get("cap_camion_tn"), "cap_camion_tn"),
            costo_por_viaje=_num(data.get("costo_por_viaje"), "costo_por_viaje"),
            camiones_disponibles=_int(data.get("camiones_disponibles", 0), "camiones_disponibles"),
            viajes_por_camion_semana=_int(data.get("viajes_por_camion_semana", 6), "viajes_por_camion_semana"))
    except ValueError as e:
        abort(400, description=str(e))
    return jsonify(serialize_transporte(pt))


@bp.get("/campanas/<int:campana_id>/transporte")
def get_transporte(campana_id):
    _, plan = _plan_o_400(campana_id)
    if plan.plan_transporte is None:
        abort(404, description="La campaña aún no tiene plan de transporte.")
    return jsonify(serialize_transporte(plan.plan_transporte))


# --------------------------- M7 Logística / inventario ---------------------------

@bp.put("/campanas/<int:campana_id>/inventario")
def set_inventario(campana_id):
    campana = get_campana_o_404(campana_id)
    bloquear_si_cerrada(campana)
    data = request.get_json(silent=True) or {}
    items = data.get("items")
    if not isinstance(items, list):
        abort(400, description="Se espera 'items' como lista de materiales.")
    try:
        derivados.set_inventario(campana, items)
    except ValueError as e:
        abort(400, description=str(e))
    return jsonify(serialize_inventario(campana))


@bp.get("/campanas/<int:campana_id>/inventario")
def get_inventario(campana_id):
    campana = get_campana_o_404(campana_id)
    return jsonify(serialize_inventario(campana))


@bp.get("/campanas/<int:campana_id>/logistica")
def get_logistica(campana_id):
    _, plan = _plan_o_400(campana_id)
    return jsonify(serialize_logistica(plan))
