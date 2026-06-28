"""
Planificación de cosecha (Módulo 5 / Fase F4).

Distribuye la producción estimada de la campaña (Σ predicciones) en semanas, siguiendo
una curva de cosecha tipo campana (sube y baja). El total de las semanas SIEMPRE cuadra
con el total predicho; reprogramar una semana redistribuye el resto en las demás.
"""
import math
from datetime import timedelta

from app.models import db, PlanCosecha, SemanaCosecha
from app.services.prediccion import total_campana


def _normalizar(crudos):
    """Normaliza una lista de pesos crudos para que sumen 1."""
    s = sum(crudos) or 1
    return [w / s for w in crudos]


def _pesos_campana(n):
    """Campana (seno): arranca bajo, pico al centro, baja al final."""
    return _normalizar([math.sin(math.pi * (i + 0.5) / n) for i in range(n)])


def _pesos_uniforme(n):
    """Plana: la misma producción cada semana (100/n)."""
    return _normalizar([1] * n)


def _pesos_creciente(n):
    """Rampa ascendente: sube semana a semana, pico al final."""
    return _normalizar([i + 1 for i in range(n)])


def _pesos_decreciente(n):
    """Rampa descendente: pico al inicio y baja hacia el final."""
    return _normalizar([n - i for i in range(n)])


# Curvas disponibles para repartir el total de la campaña (clave = valor que envía el front).
CURVAS = {
    "campana": _pesos_campana,
    "uniforme": _pesos_uniforme,
    "creciente": _pesos_creciente,
    "decreciente": _pesos_decreciente,
}


def _pesos(curva, n):
    """Devuelve los pesos (Σ=1) de la curva pedida. Lanza ValueError si no existe."""
    fn = CURVAS.get(curva)
    if fn is None:
        opciones = ", ".join(sorted(CURVAS))
        raise ValueError(f"Curva de distribución desconocida: '{curva}'. Opciones: {opciones}.")
    return fn(n)


def _recalcular_pct_y_cuadre(plan):
    """Recalcula porcentajes y absorbe el residuo de redondeo en la semana mayor."""
    semanas = sorted(plan.semanas, key=lambda s: s.numero_semana)
    if not semanas or not plan.tn_total:
        return
    suma = round(sum(s.tn_planificada or 0 for s in semanas), 2)
    residuo = round(plan.tn_total - suma, 2)
    if residuo:
        mayor = max(semanas, key=lambda s: s.tn_planificada or 0)
        mayor.tn_planificada = round((mayor.tn_planificada or 0) + residuo, 2)
    for s in semanas:
        s.porcentaje = round((s.tn_planificada or 0) / plan.tn_total * 100, 2)


def generar_plan_cosecha(campana, fecha_inicio, semanas_total, curva="campana"):
    """
    Crea (o reemplaza) el plan de cosecha de la campaña distribuyendo el total
    predicho en `semanas_total` semanas desde `fecha_inicio`, según la `curva`
    elegida (campana/uniforme/creciente/decreciente). Lanza ValueError si no hay
    predicciones o los parámetros son inválidos.
    """
    if semanas_total < 2 or semanas_total > 21:
        raise ValueError("El número de semanas debe estar entre 2 y 21.")
    pesos = _pesos(curva, semanas_total)   # valida la curva antes de tocar la BD
    tn_total = total_campana(campana)["tn_total"]
    if not tn_total or tn_total <= 0:
        raise ValueError("No hay predicciones en la campaña; predice los lotes primero.")

    # Upsert: un solo plan por campaña
    if campana.plan_cosecha:
        db.session.delete(campana.plan_cosecha)
        db.session.flush()

    plan = PlanCosecha(campana_id=campana.id, fecha_inicio=fecha_inicio,
                       semanas_total=semanas_total, tn_total=round(tn_total, 2), curva=curva)
    db.session.add(plan)
    db.session.flush()

    for i, w in enumerate(pesos):
        ini = fecha_inicio + timedelta(days=7 * i)
        plan.semanas.append(SemanaCosecha(
            numero_semana=i + 1, fecha_inicio=ini, fecha_fin=ini + timedelta(days=6),
            tn_planificada=round(tn_total * w, 2), porcentaje=round(w * 100, 2)))

    _recalcular_pct_y_cuadre(plan)
    db.session.commit()
    return plan


def reprogramar_semana(semana, nuevo_tn):
    """
    Fija la producción de una semana y redistribuye el resto en las demás
    (proporcional a su peso actual), manteniendo Σ = tn_total.
    """
    plan = semana.plan
    if nuevo_tn < 0:
        raise ValueError("La producción de la semana no puede ser negativa.")
    if nuevo_tn > plan.tn_total:
        raise ValueError("La semana no puede superar el total de la campaña.")

    otras = [s for s in plan.semanas if s.id != semana.id]
    resto = round(plan.tn_total - nuevo_tn, 2)
    base = sum(s.tn_planificada or 0 for s in otras)

    semana.tn_planificada = round(nuevo_tn, 2)
    if otras:
        for s in otras:
            proporcion = (s.tn_planificada or 0) / base if base > 0 else 1 / len(otras)
            s.tn_planificada = round(resto * proporcion, 2)

    _recalcular_pct_y_cuadre(plan)
    db.session.commit()

    # Cascada F5: reprogramar la cosecha propaga a mano de obra / logística / transporte.
    # Import local para evitar el ciclo planificacion <-> derivados.
    from app.services.derivados import recalcular_derivados
    recalcular_derivados(plan)
    return plan


def registrar_cosecha_real(semana, tn_real):
    """
    Registra la cosecha REAL de una semana (F7), para comparar real vs planificado.

    Es un dato de resultado, independiente del plan: NO redistribuye el resto ni
    dispara la cascada de recursos (esa planifica sobre lo planificado, no sobre lo
    ejecutado). `tn_real=None` borra el registro (vuelve a "sin registrar").
    """
    if tn_real is not None:
        if tn_real < 0:
            raise ValueError("La cosecha real de la semana no puede ser negativa.")
        tn_real = round(tn_real, 2)
    semana.tn_real = tn_real
    db.session.commit()
    return semana.plan
