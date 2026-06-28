"""
Servicio de predicción (Módulo 4: Inteligencia Agrícola).

Orquesta: RegistroAgronomico de (lote, campaña) -> Predictor -> persiste Prediccion.
Mantiene UNA predicción por lote+campaña (upsert con el último resultado).
"""
from flask import current_app

from app.models import (
    db, RegistroAgronomico, Prediccion, Lote, Campana, LoteCampana,
    ResultadoCosecha, utcnow,
)
from app.ml.predictor import Predictor

_predictor = None


def get_predictor():
    """Predictor singleton, cargado con la ruta de modelo de la config."""
    global _predictor
    if _predictor is None:
        _predictor = Predictor(current_app.config["ML_MODEL_PATH"])
    return _predictor


def predecir_lote(lote, campana):
    """
    Predice el rendimiento del lote en la campaña, persiste y devuelve
    (prediccion, resultado_dict). Lanza ValueError si faltan datos.
    """
    registro = RegistroAgronomico.query.filter_by(
        lote_id=lote.id, campana_id=campana.id).first()
    if registro is None:
        raise ValueError("El lote no tiene registro agronómico en esta campaña.")

    res = get_predictor().predecir(registro, lote.area_ha)

    pred = Prediccion.query.filter_by(lote_id=lote.id, campana_id=campana.id).first()
    if pred is None:
        pred = Prediccion(lote_id=lote.id, campana_id=campana.id)
        db.session.add(pred)
    pred.tn_ha_predicho = res["tn_ha"]
    pred.tn_total_predicho = res["tn_total"]
    pred.nivel_confianza = res["confianza"]
    if res.get("intervalo"):
        pred.intervalo_p10 = res["intervalo"]["p10"]
        pred.intervalo_p90 = res["intervalo"]["p90"]
    pred.fecha = utcnow()      # refrescar el timestamp también al re-predecir (upsert)
    db.session.commit()
    return pred, res


def historial_lote(lote):
    """
    Historial productivo del lote a través de las campañas en que participó.

    Por campaña: Tn/Ha REAL (ResultadoCosecha) si la cosecha está cerrada; si no,
    la predicción del modelo. Ordenado de la campaña más antigua a la más reciente.
    Devuelve [{campana_id, campana, estado, tn_ha, fuente}], con fuente ∈
    {"real", "predicho", None} (None = la campaña aún no tiene ni cosecha ni predicción).
    """
    participaciones = (
        LoteCampana.query.filter_by(lote_id=lote.id)
        .join(Campana, Campana.id == LoteCampana.campana_id)
        .order_by(Campana.fecha_inicio)
        .all()
    )
    out = []
    for lc in participaciones:
        camp = lc.campana
        cosecha = ResultadoCosecha.query.filter_by(
            lote_id=lote.id, campana_id=camp.id).first()
        if cosecha is not None:
            tn_ha, fuente = cosecha.tn_ha_real, "real"
        else:
            pred = Prediccion.query.filter_by(
                lote_id=lote.id, campana_id=camp.id).first()
            tn_ha = pred.tn_ha_predicho if pred else None
            fuente = "predicho" if pred else None
        out.append({
            "campana_id": camp.id, "campana": camp.nombre, "estado": camp.estado,
            "tn_ha": round(tn_ha, 2) if tn_ha is not None else None,
            "fuente": fuente,
        })
    return out


def total_campana(campana):
    """
    Suma las predicciones de todos los lotes de la campaña.
    Devuelve {tn_total, n_lotes, por_lote:[...]} — base del KPI de campaña.
    """
    preds = Prediccion.query.filter_by(campana_id=campana.id).all()
    tn_total = sum(p.tn_total_predicho or 0 for p in preds)
    nombres = {l.id: l.nombre for l in
               Lote.query.filter(Lote.id.in_([p.lote_id for p in preds])).all()} if preds else {}
    por_lote = [{
        "lote_id": p.lote_id,
        "lote": nombres.get(p.lote_id),
        "tn_ha": round(p.tn_ha_predicho, 2) if p.tn_ha_predicho is not None else None,
        "tn_total": round(p.tn_total_predicho, 2) if p.tn_total_predicho is not None else None,
    } for p in preds]
    return {"tn_total": round(tn_total, 2), "n_lotes": len(preds), "por_lote": por_lote}
