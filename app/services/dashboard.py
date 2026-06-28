"""
Dashboard consolidado (Fase F6 / Módulo 1).

Reúne en un solo objeto los KPIs de todos los módulos para el panel de control (estilo
Sismagro). Solo lectura: no genera ni modifica nada. Las alertas las cuenta del estado
actual (se generan aparte, bajo demanda, en `services/alertas.py`).
"""
from app.models import Alerta, LogisticaSemanal
from app.services.prediccion import total_campana


def _pico(filas, valor, numero):
    """Devuelve (valor_máximo, numero_semana) sobre una lista de filas, o (0, None)."""
    mejor = None
    for f in filas:
        v = valor(f) or 0
        if mejor is None or v > mejor[0]:
            mejor = (v, numero(f))
    return mejor or (0, None)


def resumen_dashboard(campana):
    """KPIs consolidados de la campaña: predicción, cosecha, M6/M7/M8 y alertas."""
    plan = campana.plan_cosecha
    pred = total_campana(campana)

    out = {
        "campana": {"id": campana.id, "nombre": campana.nombre, "estado": campana.estado},
        "prediccion": {
            "tn_total": pred["tn_total"],
            "n_lotes": pred["n_lotes"],
            "tn_ha_prom": round(pred["tn_total"] / sum(l.area_ha for l in _lotes(campana)), 2)
                          if pred["n_lotes"] and _area(campana) else None,
        },
        "cosecha": None, "mano_obra": None, "transporte": None, "logistica": None,
        "alertas": _kpi_alertas(campana),
    }

    if plan is None:
        return out

    semanas = sorted(plan.semanas, key=lambda s: s.numero_semana)
    tn_pico, sem_pico = _pico(semanas, lambda s: s.tn_planificada, lambda s: s.numero_semana)
    out["cosecha"] = {
        "semanas_total": plan.semanas_total, "tn_total": plan.tn_total,
        "tn_pico": round(tn_pico, 2), "semana_pico": sem_pico,
        "fecha_inicio": plan.fecha_inicio.isoformat() if plan.fecha_inicio else None,
    }

    if plan.plan_mano_obra:
        reqs = plan.plan_mano_obra.requerimientos
        cuad_pico, cs = _pico(reqs, lambda r: r.cuadrillas_req, lambda r: r.semana.numero_semana)
        out["mano_obra"] = {
            "cuadrillas_pico": cuad_pico, "semana_pico": cs,
            "jornales_total": round(sum(r.jornales_req or 0 for r in reqs), 1),
            "cuadrillas_disponibles": plan.plan_mano_obra.cuadrillas_disponibles,
            "tiene_deficit": any((r.deficit or 0) > 0 for r in reqs),
        }

    if plan.plan_transporte:
        desp = plan.plan_transporte.despachos
        cam_pico, ts = _pico(desp, lambda d: d.camiones, lambda d: d.semana.numero_semana)
        out["transporte"] = {
            "camiones_pico": cam_pico, "semana_pico": ts,
            "viajes_total": sum(d.viajes or 0 for d in desp),
            "costo_total": round(sum(d.costo or 0 for d in desp), 2),
            "camiones_disponibles": plan.plan_transporte.camiones_disponibles,
            "tiene_deficit": any((d.deficit or 0) > 0 for d in desp),
        }

    semana_ids = [s.id for s in semanas]
    logs = (LogisticaSemanal.query.filter(LogisticaSemanal.semana_id.in_(semana_ids)).all()
            if semana_ids else [])
    if logs:
        materiales = sorted({log.material for log in logs})
        out["logistica"] = {
            "materiales": materiales,
            "tiene_deficit": any((log.deficit or 0) > 0 for log in logs),
        }

    return out


def _lotes(campana):
    # Lotes con predicción en la campaña (para el promedio ponderado por área).
    ids = {p.lote_id for p in campana.predicciones}
    from app.models import Lote
    return Lote.query.filter(Lote.id.in_(ids)).all() if ids else []


def _area(campana):
    return sum(l.area_ha or 0 for l in _lotes(campana))


def _kpi_alertas(campana):
    """Conteo de alertas activas por severidad (badge del panel)."""
    activas = Alerta.query.filter_by(campana_id=campana.id, estado="activa").all()
    por_sev = {"alta": 0, "media": 0, "baja": 0}
    for a in activas:
        por_sev[a.severidad] = por_sev.get(a.severidad, 0) + 1
    return {"activas": len(activas), "por_severidad": por_sev}
