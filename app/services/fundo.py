"""
Agregación GLOBAL del fundo (Panel de Control Global / alta gerencia).

A diferencia de `services/dashboard.py` (KPIs de UNA campaña), aquí se cruzan
TODAS las campañas para dar la foto histórica de la unidad productiva:
área total, producción acumulada, rendimiento global, tendencia interanual y
consolidado de recursos. Solo lectura: no genera ni modifica nada.

Producción por campaña: si hay cosecha real (ResultadoCosecha.tn_ha_real) se usa
ese tonelaje (dato comercializado); si la campaña aún no tiene cosecha cerrada,
cae a la predicción del modelo, marcada como 'proyectada'.
"""
from app.models import Campana, Lote, Finca
from app.services.prediccion import total_campana


def _areas_por_lote():
    return {l.id: (l.area_ha or 0) for l in Lote.query.all()}


def _produccion_campana(campana, areas):
    """(tn_total, area_productiva_ha, tipo) de una campaña.

    tipo='real' si hay cosecha cerrada; 'proyectada' si se usa la predicción.
    """
    cosechas = campana.cosechas
    if cosechas:
        tn_total = sum((rc.tn_ha_real or 0) * areas.get(rc.lote_id, 0) for rc in cosechas)
        area = sum(areas.get(rc.lote_id, 0) for rc in cosechas)
        return round(tn_total, 2), round(area, 4), "real"
    pred = total_campana(campana)
    area = sum(areas.get(p["lote_id"], 0) for p in pred["por_lote"])
    return pred["tn_total"], round(area, 4), "proyectada"


def resumen_fundo():
    """KPIs y series consolidadas del fundo a través de todas las campañas."""
    areas = _areas_por_lote()
    area_total_ha = round(sum(areas.values()), 4)

    campanas = Campana.query.order_by(Campana.fecha_inicio).all()

    tendencia = []
    historico_tn = 0.0
    area_acumulada = 0.0
    jornales_acumulados = 0.0
    costo_logistico_acumulado = 0.0

    for c in campanas:
        tn_total, area, tipo = _produccion_campana(c, areas)
        tn_ha = round(tn_total / area, 2) if area else None
        tendencia.append({
            "campana_id": c.id, "nombre": c.nombre, "estado": c.estado,
            "tn_total": tn_total, "tn_ha": tn_ha, "tipo": tipo,
        })
        historico_tn += tn_total
        area_acumulada += area

        plan = c.plan_cosecha
        if plan and plan.plan_mano_obra:
            jornales_acumulados += sum(r.jornales_req or 0 for r in plan.plan_mano_obra.requerimientos)
        if plan and plan.plan_transporte:
            costo_logistico_acumulado += sum(d.costo or 0 for d in plan.plan_transporte.despachos)

    finca = Finca.query.first()
    return {
        "fundo": {"id": finca.id, "nombre": finca.nombre, "distrito": finca.distrito} if finca else None,
        "area_total_ha": area_total_ha,
        "historico_tn": round(historico_tn, 2),
        "tn_ha_global": round(historico_tn / area_acumulada, 2) if area_acumulada else None,
        "n_campanas": len(campanas),
        "tendencia": tendencia,
        "recursos": {
            "jornales_acumulados": round(jornales_acumulados, 1),
            "costo_logistico_acumulado": round(costo_logistico_acumulado, 2),
        },
    }
