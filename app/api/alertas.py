"""
Alertas + Dashboard (Fase F6 / Módulos 9 y 1).

POST /campanas/<id>/alertas/generar  -> (re)genera las alertas de déficit (bajo demanda)
GET  /campanas/<id>/alertas[?estado=activa]  -> lista las alertas (ordenadas por severidad)
PUT  /alertas/<id>                   -> resuelve / reactiva una alerta
GET  /campanas/<id>/dashboard        -> KPIs consolidados de todos los módulos
"""
from flask import Blueprint, jsonify, request, abort

from app.models import db, Alerta
from app.services import alertas as svc
from app.services.dashboard import resumen_dashboard
from app.api._common import get_campana_o_404, bloquear_si_cerrada, serialize_alerta

bp = Blueprint("alertas", __name__)

_ORDEN_SEV = {"alta": 0, "media": 1, "baja": 2}


def _ordenadas(alertas):
    """Más graves primero; dentro de la misma severidad, por semana."""
    return sorted(alertas, key=lambda a: (_ORDEN_SEV.get(a.severidad, 9), a.semana_id or 0))


@bp.post("/campanas/<int:campana_id>/alertas/generar")
def generar(campana_id):
    campana = get_campana_o_404(campana_id)
    bloquear_si_cerrada(campana)
    nuevas = svc.generar_alertas(campana)
    return jsonify([serialize_alerta(a) for a in _ordenadas(nuevas)]), 201


@bp.get("/campanas/<int:campana_id>/alertas")
def listar(campana_id):
    campana = get_campana_o_404(campana_id)
    q = Alerta.query.filter_by(campana_id=campana.id)
    estado = request.args.get("estado")
    if estado:
        q = q.filter_by(estado=estado)
    return jsonify([serialize_alerta(a) for a in _ordenadas(q.all())])


@bp.put("/alertas/<int:alerta_id>")
def actualizar(alerta_id):
    alerta = Alerta.query.get_or_404(alerta_id)
    data = request.get_json(silent=True) or {}
    estado = data.get("estado", "resuelta")
    if estado not in ("activa", "resuelta"):
        abort(400, description="'estado' debe ser 'activa' o 'resuelta'.")
    alerta.estado = estado
    db.session.commit()
    return jsonify(serialize_alerta(alerta))


@bp.get("/campanas/<int:campana_id>/dashboard")
def dashboard(campana_id):
    campana = get_campana_o_404(campana_id)
    return jsonify(resumen_dashboard(campana))
