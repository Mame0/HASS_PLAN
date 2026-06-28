"""
Panel de Control Global del fundo (analítica histórica multi-campaña).

GET /fundo/dashboard -> KPIs consolidados + tendencia interanual + recursos acumulados.
"""
from flask import Blueprint, jsonify, request

from app.services.fundo import resumen_fundo

bp = Blueprint("fundo", __name__)


@bp.get("/fundo/dashboard")
def dashboard_global():
    # Acota el panel a una finca (la seleccionada en el front) o, sin el parámetro,
    # da la foto global del tenant. RLS ya garantiza que solo se vean fincas propias.
    finca_id = request.args.get("finca_id", type=int)
    return jsonify(resumen_fundo(finca_id))
