"""
Variables del lote (manual + API) para una campaña.

GET  /lotes/<id>/variables          -> 5 manuales + 12 climáticas con estado de sync
PUT  /lotes/<id>/variables/<key>    -> override/edición manual de una variable
"""
from flask import Blueprint, jsonify, request, abort

from app.models import db, Lote, ResultadoCosecha, VariableOverride
from app.api._common import (
    VAR_META, API_KEYS, HARVEST_KEYS,
    get_campana, bloquear_si_cerrada, get_or_create_registro, serialize_variables,
    validar_lote_en_campana,
)

bp = Blueprint("variables", __name__)


@bp.get("/lotes/<int:lote_id>/variables")
def get_variables(lote_id):
    lote = Lote.query.get_or_404(lote_id)
    campana = get_campana(request.args.get("campana_id", type=int))
    if campana is None:
        abort(404, description="No hay campaña disponible.")
    validar_lote_en_campana(lote, campana)
    return jsonify(serialize_variables(lote, campana))


@bp.put("/lotes/<int:lote_id>/variables/<key>")
def set_variable(lote_id, key):
    if key not in VAR_META:
        abort(400, description=f"Variable desconocida: {key}")
    lote = Lote.query.get_or_404(lote_id)
    campana = get_campana(request.args.get("campana_id", type=int))
    if campana is None:
        abort(404, description="No hay campaña disponible.")
    validar_lote_en_campana(lote, campana)
    bloquear_si_cerrada(campana)

    data = request.get_json(silent=True) or {}
    valor = data.get("valor")
    motivo = data.get("motivo", "edición manual")

    # Validación de manuales numéricas: edades y riego no pueden ser negativos.
    if key in ("edad_campo", "edad_prod", "riego_m3ha") and valor is not None:
        try:
            if float(valor) < 0:
                abort(400, description=f"'{key}' no puede ser negativo.")
        except (ValueError, TypeError):
            abort(400, description=f"'{key}' debe ser numérico.")

    reg = get_or_create_registro(lote, campana)

    if key in HARVEST_KEYS:
        # Vive en ResultadoCosecha (dato de muestreo pre-cosecha)
        cosecha = ResultadoCosecha.query.filter_by(
            lote_id=lote.id, campana_id=campana.id).first()
        if cosecha is None:
            cosecha = ResultadoCosecha(lote_id=lote.id, campana_id=campana.id, tn_ha_real=0)
            db.session.add(cosecha)
        setattr(cosecha, key, valor)
    else:
        setattr(reg, key, valor)
        # Si es una variable climática, registrar el override para que el sync no la pise
        if key in API_KEYS:
            ov = VariableOverride.query.filter_by(registro_id=reg.id, var_key=key).first()
            if ov is None:
                ov = VariableOverride(registro_id=reg.id, var_key=key)
                db.session.add(ov)
            ov.valor = valor
            ov.motivo = motivo

    db.session.commit()
    return jsonify(serialize_variables(lote, campana))
