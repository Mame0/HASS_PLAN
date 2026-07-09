"""
Servicio de RESULTADO DE COSECHA (F7 — cierre y validación del modelo).

Carga la cosecha REAL por lote (Tn/Ha real, y opcionalmente frutos/árbol y peso de
fruto — datos que solo se conocen al cosechar, por eso NO son features del modelo) y
la compara contra la predicción del RF: predicho vs real, error absoluto (Tn/Ha) y
error relativo (%). Agrega el MAE y el MAPE de la campaña, que es la métrica con la
que la tesis valida el modelo en La Joya y decide si recalibrar.

Mantiene UN ResultadoCosecha por lote+campaña (upsert). No conoce Flask (capa service).
"""
from datetime import date

from app.models import (
    db, ResultadoCosecha, Prediccion, Lote, LoteCampana,
)


def _num_opt(valor, campo):
    """Convierte a float un opcional; '' / None -> None. No negativo."""
    if valor is None or valor == "":
        return None
    try:
        f = float(valor)
    except (ValueError, TypeError):
        raise ValueError(f"'{campo}' debe ser numérico.")
    if f < 0:
        raise ValueError(f"'{campo}' no puede ser negativo.")
    return f


def _parse_fecha(valor):
    if not valor:
        return date.today()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError:
        raise ValueError("La fecha de cierre debe tener formato AAAA-MM-DD.")


def _lotes_de_campana(campana_id):
    """Lotes asociados a la campaña (por LoteCampana), ordenados por id."""
    lcs = (LoteCampana.query.filter_by(campana_id=campana_id)
           .join(Lote, Lote.id == LoteCampana.lote_id)
           .order_by(Lote.id).all())
    return [lc.lote for lc in lcs]


def guardar_resultado(lote, campana, tn_ha_real, frutos_arbol=None,
                      peso_fruto=None, fecha_cierre=None):
    """Upsert del ResultadoCosecha de (lote, campaña). tn_ha_real es obligatorio (> 0)."""
    if tn_ha_real is None or tn_ha_real == "":
        raise ValueError("El rendimiento real (Tn/Ha) es obligatorio.")
    try:
        tn = float(tn_ha_real)
    except (ValueError, TypeError):
        raise ValueError("El rendimiento real (Tn/Ha) debe ser numérico.")
    if tn <= 0:
        raise ValueError("El rendimiento real (Tn/Ha) debe ser mayor que 0.")

    rc = ResultadoCosecha.query.filter_by(lote_id=lote.id, campana_id=campana.id).first()
    if rc is None:
        rc = ResultadoCosecha(lote_id=lote.id, campana_id=campana.id)
        db.session.add(rc)
    rc.tn_ha_real = tn
    rc.frutos_arbol = _num_opt(frutos_arbol, "frutos_arbol")
    rc.peso_fruto = _num_opt(peso_fruto, "peso_fruto")
    rc.fecha_cierre = _parse_fecha(fecha_cierre)
    db.session.commit()
    return rc


def borrar_resultado(lote, campana):
    """Borra el ResultadoCosecha del lote en la campaña. Devuelve True si existía."""
    rc = ResultadoCosecha.query.filter_by(lote_id=lote.id, campana_id=campana.id).first()
    if rc is None:
        return False
    db.session.delete(rc)
    db.session.commit()
    return True


def serialize_resultado(rc):
    return {
        "lote_id": rc.lote_id, "campana_id": rc.campana_id,
        "tn_ha_real": rc.tn_ha_real,
        "frutos_arbol": rc.frutos_arbol, "peso_fruto": rc.peso_fruto,
        "fecha_cierre": rc.fecha_cierre.isoformat() if rc.fecha_cierre else None,
    }


def comparacion_campana(campana):
    """
    Predicho vs real por lote de la campaña + métricas agregadas.

    Devuelve {por_lote:[...], resumen:{n_lotes, n_con_real, n_comparables, mae, mape}}.
      - error_abs  = |real - predicho|           (Tn/Ha)
      - error_pct  = error_abs / real * 100       (%)
      - MAE  = promedio de error_abs de los lotes comparables (predicho Y real)
      - MAPE = promedio de error_pct de esos lotes
    """
    lotes = _lotes_de_campana(campana.id)
    preds = {p.lote_id: p for p in Prediccion.query.filter_by(campana_id=campana.id).all()}
    reales = {r.lote_id: r for r in ResultadoCosecha.query.filter_by(campana_id=campana.id).all()}

    por_lote, errs_abs, errs_pct = [], [], []
    for l in lotes:
        p = preds.get(l.id)
        r = reales.get(l.id)
        pred_tn = round(p.tn_ha_predicho, 2) if p and p.tn_ha_predicho is not None else None
        real_tn = round(r.tn_ha_real, 2) if r else None
        err_abs = err_pct = None
        if pred_tn is not None and real_tn is not None:
            ea = abs(r.tn_ha_real - p.tn_ha_predicho)
            err_abs = round(ea, 2)
            errs_abs.append(ea)
            if r.tn_ha_real:
                ep = ea / r.tn_ha_real * 100
                err_pct = round(ep, 1)
                errs_pct.append(ep)
        por_lote.append({
            "lote_id": l.id, "lote": l.nombre, "area_ha": l.area_ha,
            "tn_ha_predicho": pred_tn, "tn_ha_real": real_tn,
            "frutos_arbol": r.frutos_arbol if r else None,
            "peso_fruto": r.peso_fruto if r else None,
            "fecha_cierre": r.fecha_cierre.isoformat() if r and r.fecha_cierre else None,
            "error_abs": err_abs, "error_pct": err_pct,
            "tiene_prediccion": p is not None, "tiene_real": r is not None,
        })

    n_comp = len(errs_abs)
    resumen = {
        "n_lotes": len(lotes),
        "n_con_real": sum(1 for l in lotes if l.id in reales),
        "n_comparables": n_comp,
        "mae": round(sum(errs_abs) / n_comp, 2) if n_comp else None,
        "mape": round(sum(errs_pct) / len(errs_pct), 1) if errs_pct else None,
    }
    return {"por_lote": por_lote, "resumen": resumen}
