"""
Servicio de predicción (Módulo 4: Inteligencia Agrícola).

Orquesta: RegistroAgronomico de (lote, campaña) -> Predictor -> persiste Prediccion.
Mantiene UNA predicción por lote+campaña (upsert con el último resultado).

RECALIBRACIÓN PROGRESIVA (jul-2026)
-----------------------------------
El modelo se entrena en Nepeña y se despliega en La Joya: acierta razonablemente el
ORDEN de los lotes (correlación de orden ~0.37) pero no su NIVEL, porque la mitad de
la variabilidad del rendimiento es el efecto del año y ninguna variable lo captura.

La cosecha no ocurre de golpe: dura 16–20 semanas y avanza lote a lote. En cuanto hay
unos pocos lotes cosechados se conoce el nivel REAL de la campaña, y ese dato corrige
las predicciones de los que faltan:

    factor = Σ real(lotes cosechados) / Σ predicho(esos mismos lotes)

Sobre validación dejando una campaña fuera, recalibrar con 5 lotes baja el MAPE del
51 % al 36 % y sube el R² de +0.15 a +0.40. No requiere reentrenar ni datos nuevos:
usa exactamente lo que F7 ya obliga a registrar.

`total_campana` aplica el factor a los lotes pendientes y usa el valor REAL en los ya
cosechados, así que el plan de cosecha (F4) y toda la cascada F5 se apoyan en el mejor
estimado disponible en cada momento, no en el del día 1.
"""
from flask import current_app

from app.models import (
    db, RegistroAgronomico, Prediccion, Lote, Campana, LoteCampana,
    ResultadoCosecha, utcnow,
)
from app.ml.predictor import Predictor

_predictor = None

# Nº mínimo de lotes cosechados para estimar el nivel de la campaña. Con menos de 3
# el factor lo domina el ruido de un solo lote atípico.
MIN_LOTES_RECALIBRACION = 3
# Tope de seguridad: un factor fuera de este rango indica un dato mal cargado
# (unidades equivocadas, un tn_ha_real de otra escala), no un año excepcional.
FACTOR_MIN, FACTOR_MAX = 0.5, 2.0


def _r2(v):
    """Redondeo a 2 decimales tolerante a None (la API sirve None, no 0)."""
    return round(v, 2) if v is not None else None


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


def factor_recalibracion(campana):
    """
    Factor de nivel de la campaña estimado con los lotes YA cosechados.

    Devuelve {factor, n_lotes, aplicable, motivo}. `factor` es 1.0 (neutro) mientras
    no haya evidencia suficiente, de modo que quien lo consuma puede multiplicar
    siempre sin ramificar.

    Solo cuenta un lote si tiene cosecha real > 0 Y predicción. El filtro `> 0` no es
    cosmético: la ruta de variables crea un ResultadoCosecha con tn_ha_real=0 al
    guardar solo frutos/árbol (muestreo pre-cosecha), y ese cero envenenaría el factor.
    """
    reales = {rc.lote_id: rc.tn_ha_real
              for rc in ResultadoCosecha.query.filter(
                  ResultadoCosecha.campana_id == campana.id,
                  ResultadoCosecha.tn_ha_real > 0).all()}
    if not reales:
        return {"factor": 1.0, "n_lotes": 0, "aplicable": False,
                "motivo": "Aún no hay lotes cosechados en esta campaña."}

    preds = {p.lote_id: p.tn_ha_predicho
             for p in Prediccion.query.filter(
                 Prediccion.campana_id == campana.id,
                 Prediccion.lote_id.in_(reales)).all()
             if p.tn_ha_predicho}
    comunes = [l for l in preds if l in reales]

    if len(comunes) < MIN_LOTES_RECALIBRACION:
        return {"factor": 1.0, "n_lotes": len(comunes), "aplicable": False,
                "motivo": (f"Se necesitan {MIN_LOTES_RECALIBRACION} lotes con cosecha real "
                           f"y predicción; hay {len(comunes)}.")}

    suma_pred = sum(preds[l] for l in comunes)
    if suma_pred <= 0:
        return {"factor": 1.0, "n_lotes": len(comunes), "aplicable": False,
                "motivo": "Las predicciones de los lotes cosechados suman cero."}

    bruto = sum(reales[l] for l in comunes) / suma_pred
    factor = min(FACTOR_MAX, max(FACTOR_MIN, bruto))
    fuera = abs(bruto - factor) > 1e-9
    return {
        "factor": round(factor, 4),
        "factor_bruto": round(bruto, 4),
        "n_lotes": len(comunes),
        "aplicable": True,
        "motivo": (f"Nivel ajustado con {len(comunes)} lote(s) ya cosechado(s)."
                   + (f" Recortado al tope de seguridad ({FACTOR_MIN}–{FACTOR_MAX}): "
                      f"revisa las unidades de la cosecha cargada." if fuera else "")),
    }


def total_campana(campana):
    """
    Producción estimada de la campaña, lote a lote.

    Para cada lote usa, por orden de preferencia:
      1. la cosecha REAL si ya se registró (fuente "real"),
      2. la predicción CORREGIDA por el factor de nivel (fuente "recalibrado"),
      3. la predicción cruda si aún no hay factor (fuente "predicho").

    Devuelve {tn_total, tn_total_crudo, n_lotes, recalibracion, por_lote:[...]}.
    `tn_total` es el que consume el plan de cosecha (F4) y la cascada F5.
    """
    preds = Prediccion.query.filter_by(campana_id=campana.id).all()
    recal = factor_recalibracion(campana)
    factor = recal["factor"]

    reales = {rc.lote_id: rc.tn_ha_real
              for rc in ResultadoCosecha.query.filter(
                  ResultadoCosecha.campana_id == campana.id,
                  ResultadoCosecha.tn_ha_real > 0).all()}
    lotes = {l.id: l for l in
             Lote.query.filter(Lote.id.in_([p.lote_id for p in preds])).all()} if preds else {}

    def resolver(p):
        """(tn_ha, fuente) del lote: real > recalibrado > predicho."""
        if p.lote_id in reales:
            return reales[p.lote_id], "real"
        if recal["aplicable"] and p.tn_ha_predicho is not None:
            return p.tn_ha_predicho * factor, "recalibrado"
        return p.tn_ha_predicho, "predicho"

    def fila(p):
        """Fila de `por_lote` + (tn_total del lote, tn_total crudo del lote)."""
        lote = lotes.get(p.lote_id)
        area = (lote.area_ha if lote else None) or 0
        crudo = p.tn_total_predicho or 0
        tn_ha, fuente = resolver(p)
        total = tn_ha * area if (tn_ha is not None and area) else crudo
        return {
            "lote_id": p.lote_id,
            "lote": lote.nombre if lote else None,
            "tn_ha": _r2(tn_ha),
            "tn_total": _r2(total),
            "tn_ha_predicho": _r2(p.tn_ha_predicho),
            "fuente": fuente,
        }, (total or 0), crudo

    por_lote, tn_total, tn_crudo = [], 0.0, 0.0
    for p in preds:
        f, total, crudo = fila(p)
        por_lote.append(f)
        tn_total += total
        tn_crudo += crudo

    return {
        "tn_total": round(tn_total, 2),
        "tn_total_crudo": round(tn_crudo, 2),
        "n_lotes": len(preds),
        "recalibracion": recal,
        "por_lote": por_lote,
    }
