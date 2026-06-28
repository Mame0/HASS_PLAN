"""
Módulos derivados de la cosecha (Fase F5): Mano de Obra (M6), Logística (M7) y
Transporte (M8). Los tres consumen las semanas del Plan de Cosecha (F4): a partir de
`tn_planificada` por semana calculan jornales/cuadrillas, materiales y camiones/viajes,
y marcan el **déficit** cuando lo requerido supera lo disponible.

Cascada: `recalcular_derivados(plan)` se invoca tras reprogramar una semana de cosecha,
de modo que cambiar el plan propaga automáticamente a los tres módulos.

Fórmulas (acordadas jun-2026):
  M6  jornales_req   = tn_semana / rendimiento_jornal
      cuadrillas_req = ceil(jornales_req / (tam_cuadrilla · dias_cosecha_semana))
      deficit        = max(0, cuadrillas_req - cuadrillas_disponibles)
  M7  requerido      = tn_semana · consumo_por_tn          (por material del inventario)
      deficit        = max(0, requerido - cantidad_disponible)   (pico semanal vs stock)
  M8  viajes         = ceil(tn_semana / cap_camion_tn)
      camiones_req   = ceil(viajes / viajes_por_camion_semana)
      costo          = viajes · costo_por_viaje
      deficit        = max(0, camiones_req - camiones_disponibles)
"""
import math

from app.models import (
    db, PlanManoObra, ManoObraSemanal, Inventario, LogisticaSemanal,
    PlanTransporte, DespachoSemanal,
)


def _ceil(x):
    """Techo robusto a ruido de coma flotante (12.00000001 -> 12, no 13)."""
    return int(math.ceil(round(x, 6)))


def _semanas(plan):
    return sorted(plan.semanas, key=lambda s: s.numero_semana)


# ---------------------------------------------------------------------------
#  M6 — Mano de obra
# ---------------------------------------------------------------------------

def configurar_mano_obra(plan, rendimiento_jornal, tam_cuadrilla,
                         cuadrillas_disponibles=0, dias_cosecha_semana=6):
    """Crea/actualiza el PlanManoObra de un plan de cosecha y recalcula sus semanas."""
    if rendimiento_jornal is None or rendimiento_jornal <= 0:
        raise ValueError("El rendimiento por jornal debe ser > 0.")
    if tam_cuadrilla is None or tam_cuadrilla < 1:
        raise ValueError("El tamaño de cuadrilla debe ser ≥ 1.")
    if dias_cosecha_semana is None or dias_cosecha_semana < 1:
        raise ValueError("Los días de cosecha por semana deben ser ≥ 1.")
    if cuadrillas_disponibles is None or cuadrillas_disponibles < 0:
        raise ValueError("Las cuadrillas disponibles no pueden ser negativas.")

    pmo = plan.plan_mano_obra or PlanManoObra(plan_cosecha_id=plan.id)
    pmo.rendimiento_jornal = rendimiento_jornal
    pmo.tam_cuadrilla = tam_cuadrilla
    pmo.cuadrillas_disponibles = cuadrillas_disponibles
    pmo.dias_cosecha_semana = dias_cosecha_semana
    if pmo.id is None:
        db.session.add(pmo)
    db.session.flush()
    _recalcular_mano_obra(plan, pmo)
    db.session.commit()
    return pmo


def _recalcular_mano_obra(plan, pmo):
    """Reconstruye las filas ManoObraSemanal del plan (no hace commit)."""
    for r in list(pmo.requerimientos):
        db.session.delete(r)
    db.session.flush()
    for s in _semanas(plan):
        jornales = (s.tn_planificada or 0) / pmo.rendimiento_jornal
        cuadrillas = _ceil(jornales / (pmo.tam_cuadrilla * pmo.dias_cosecha_semana))
        deficit = max(0, cuadrillas - (pmo.cuadrillas_disponibles or 0))
        db.session.add(ManoObraSemanal(
            plan_id=pmo.id, semana_id=s.id,
            jornales_req=round(jornales, 2), cuadrillas_req=cuadrillas, deficit=deficit))


# ---------------------------------------------------------------------------
#  M7 — Logística / inventario
# ---------------------------------------------------------------------------

def set_inventario(campana, items):
    """
    Reemplaza el inventario de materiales de la campaña por `items` y recalcula
    la logística semanal si la campaña ya tiene plan de cosecha.
    `items`: lista de dicts {material, cantidad_disponible, unidad, consumo_por_tn}.
    """
    limpios = []
    for it in items:
        material = (it.get("material") or "").strip()
        if not material:
            raise ValueError("Cada material necesita un nombre.")
        try:
            disponible = float(it.get("cantidad_disponible") or 0)
            consumo = float(it.get("consumo_por_tn") or 0)
        except (ValueError, TypeError):
            raise ValueError(f"Las cantidades de '{material}' deben ser numéricas.")
        if disponible < 0 or consumo < 0:
            raise ValueError("Cantidad disponible y consumo por Tn no pueden ser negativos.")
        limpios.append({"material": material, "cantidad_disponible": disponible,
                        "unidad": it.get("unidad"), "consumo_por_tn": consumo})

    for inv in list(campana.inventario):
        db.session.delete(inv)
    db.session.flush()
    for it in limpios:
        db.session.add(Inventario(campana_id=campana.id, **it))
    db.session.flush()

    if campana.plan_cosecha:
        _recalcular_logistica(campana.plan_cosecha)
    db.session.commit()
    return campana.inventario


def _recalcular_logistica(plan):
    """Reconstruye las filas LogisticaSemanal (material × semana) del plan."""
    # Query directo a BD (no la colección en memoria, que puede ir desfasada tras un flush).
    inventario = Inventario.query.filter_by(campana_id=plan.campana_id).all()
    # Borrar logística previa de las semanas del plan
    semana_ids = [s.id for s in plan.semanas]
    if semana_ids:
        (LogisticaSemanal.query
         .filter(LogisticaSemanal.semana_id.in_(semana_ids))
         .delete(synchronize_session=False))
    db.session.flush()

    for s in _semanas(plan):
        for inv in inventario:
            requerido = (s.tn_planificada or 0) * (inv.consumo_por_tn or 0)
            deficit = max(0.0, requerido - (inv.cantidad_disponible or 0))
            db.session.add(LogisticaSemanal(
                semana_id=s.id, material=inv.material,
                cantidad_requerida=round(requerido, 2), deficit=round(deficit, 2)))


# ---------------------------------------------------------------------------
#  M8 — Transporte
# ---------------------------------------------------------------------------

def configurar_transporte(plan, cap_camion_tn, costo_por_viaje,
                          camiones_disponibles=0, viajes_por_camion_semana=6):
    """Crea/actualiza el PlanTransporte de un plan de cosecha y recalcula sus despachos."""
    if cap_camion_tn is None or cap_camion_tn <= 0:
        raise ValueError("La capacidad del camión debe ser > 0.")
    if costo_por_viaje is None or costo_por_viaje < 0:
        raise ValueError("El costo por viaje no puede ser negativo.")
    if viajes_por_camion_semana is None or viajes_por_camion_semana < 1:
        raise ValueError("Los viajes por camión a la semana deben ser ≥ 1.")
    if camiones_disponibles is None or camiones_disponibles < 0:
        raise ValueError("Los camiones disponibles no pueden ser negativos.")

    pt = plan.plan_transporte or PlanTransporte(plan_cosecha_id=plan.id)
    pt.cap_camion_tn = cap_camion_tn
    pt.costo_por_viaje = costo_por_viaje
    pt.camiones_disponibles = camiones_disponibles
    pt.viajes_por_camion_semana = viajes_por_camion_semana
    if pt.id is None:
        db.session.add(pt)
    db.session.flush()
    _recalcular_transporte(plan, pt)
    db.session.commit()
    return pt


def _recalcular_transporte(plan, pt):
    """Reconstruye las filas DespachoSemanal del plan (no hace commit)."""
    for d in list(pt.despachos):
        db.session.delete(d)
    db.session.flush()
    for s in _semanas(plan):
        tn = s.tn_planificada or 0
        viajes = _ceil(tn / pt.cap_camion_tn) if tn > 0 else 0
        camiones = _ceil(viajes / pt.viajes_por_camion_semana) if viajes > 0 else 0
        deficit = max(0, camiones - (pt.camiones_disponibles or 0))
        db.session.add(DespachoSemanal(
            plan_id=pt.id, semana_id=s.id, tn_despachadas=round(tn, 2),
            viajes=viajes, camiones=camiones,
            costo=round(viajes * pt.costo_por_viaje, 2), deficit=deficit))


# ---------------------------------------------------------------------------
#  Cascada
# ---------------------------------------------------------------------------

def recalcular_derivados(plan):
    """
    Recalcula los módulos derivados que ya estén configurados para `plan`.
    Se llama tras reprogramar una semana de cosecha (propagación del gate F5).
    """
    if plan is None:
        return
    if plan.plan_mano_obra:
        _recalcular_mano_obra(plan, plan.plan_mano_obra)
    if plan.plan_transporte:
        _recalcular_transporte(plan, plan.plan_transporte)
    if Inventario.query.filter_by(campana_id=plan.campana_id).count():
        _recalcular_logistica(plan)
    db.session.commit()
