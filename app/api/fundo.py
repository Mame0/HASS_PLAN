"""
Panel de Control Global del fundo (analítica histórica multi-campaña).

GET /fundo/dashboard -> KPIs consolidados + tendencia interanual + recursos acumulados.
"""
from flask import Blueprint, jsonify

from app.services.fundo import resumen_fundo

bp = Blueprint("fundo", __name__)


@bp.get("/fundo/dashboard")
def dashboard_global():
    return jsonify(resumen_fundo())
