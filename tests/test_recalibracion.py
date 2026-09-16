"""
Pruebas de la RECALIBRACIÓN PROGRESIVA y del INTERVALO CONFORMAL.

Recalibración: a medida que se cierra la cosecha de cada lote, el nivel real de la
campaña corrige las predicciones de los lotes que faltan. Es la pieza que compensa
que el modelo acierte el ORDEN de los lotes pero no su NIVEL (el efecto del año no
lo captura ninguna variable de entrada).

Conformal: el intervalo que ve el productor debe declarar si está calibrado. Un
intervalo sin calibrar NO puede presentarse con una cobertura prometida.
"""
from datetime import date

import pytest

from app.models import db, Finca, Lote, Campana, LoteCampana, Prediccion, ResultadoCosecha
from app.services.prediccion import (
    factor_recalibracion, total_campana, MIN_LOTES_RECALIBRACION, FACTOR_MIN, FACTOR_MAX,
)


def _campana(app, n_lotes=6, area=10.0, tn_ha_predicho=20.0):
    """Campaña activa con n lotes, todos con predicción de `tn_ha_predicho`."""
    with app.app_context():
        f = Finca(nombre="Chacra La Joya", distrito="La Joya")
        db.session.add(f)
        db.session.flush()
        c = Campana(nombre="24-25", finca_id=f.id, fecha_inicio=date(2024, 7, 1),
                    fecha_fin=date(2025, 6, 30), estado="activa")
        db.session.add(c)
        db.session.flush()
        ids = []
        for i in range(n_lotes):
            lote = Lote(finca_id=f.id, nombre=f"L{i}", area_ha=area)
            db.session.add(lote)
            db.session.flush()
            db.session.add(LoteCampana(lote_id=lote.id, campana_id=c.id, en_produccion=True))
            db.session.add(Prediccion(
                lote_id=lote.id, campana_id=c.id,
                tn_ha_predicho=tn_ha_predicho,
                tn_total_predicho=tn_ha_predicho * area))
            ids.append(lote.id)
        db.session.commit()
        return c.id, ids


def _cosechar(app, campana_id, lote_ids, tn_ha_real):
    with app.app_context():
        for lid in lote_ids:
            db.session.add(ResultadoCosecha(
                lote_id=lid, campana_id=campana_id,
                tn_ha_real=tn_ha_real, fecha_cierre=date(2025, 3, 1)))
        db.session.commit()


# --------------------------------------------------------------------------- #
#  Factor de recalibración
# --------------------------------------------------------------------------- #

def test_sin_cosecha_el_factor_es_neutro(app):
    """Sin lotes cosechados no hay evidencia: factor 1.0 y no aplicable."""
    cid, _ = _campana(app)
    with app.app_context():
        r = factor_recalibracion(db.session.get(Campana, cid))
    assert r["aplicable"] is False
    assert r["factor"] == 1.0
    assert r["n_lotes"] == 0


def test_no_recalibra_por_debajo_del_minimo(app):
    """Con menos lotes que el mínimo el factor sigue neutro (evita el ruido de 1 lote)."""
    cid, ids = _campana(app)
    _cosechar(app, cid, ids[:MIN_LOTES_RECALIBRACION - 1], tn_ha_real=30.0)
    with app.app_context():
        r = factor_recalibracion(db.session.get(Campana, cid))
    assert r["aplicable"] is False
    assert r["factor"] == 1.0
    assert r["n_lotes"] == MIN_LOTES_RECALIBRACION - 1


def test_factor_corrige_el_nivel_al_alza(app):
    """Predicho 20, real 26 en 3 lotes -> factor 1.3."""
    cid, ids = _campana(app, tn_ha_predicho=20.0)
    _cosechar(app, cid, ids[:3], tn_ha_real=26.0)
    with app.app_context():
        r = factor_recalibracion(db.session.get(Campana, cid))
    assert r["aplicable"] is True
    assert r["n_lotes"] == 3
    assert r["factor"] == pytest.approx(1.3, abs=1e-3)


def test_factor_corrige_el_nivel_a_la_baja(app):
    """Un año malo: predicho 20, real 14 -> factor 0.7."""
    cid, ids = _campana(app, tn_ha_predicho=20.0)
    _cosechar(app, cid, ids[:4], tn_ha_real=14.0)
    with app.app_context():
        r = factor_recalibracion(db.session.get(Campana, cid))
    assert r["factor"] == pytest.approx(0.7, abs=1e-3)


def test_factor_se_recorta_al_tope_de_seguridad(app):
    """Un real 10x el predicho es un error de unidades, no un año excepcional."""
    cid, ids = _campana(app, tn_ha_predicho=20.0)
    _cosechar(app, cid, ids[:3], tn_ha_real=200.0)
    with app.app_context():
        r = factor_recalibracion(db.session.get(Campana, cid))
    assert r["factor"] == FACTOR_MAX
    assert r["factor_bruto"] == pytest.approx(10.0, abs=1e-3)
    assert "unidades" in r["motivo"]


def test_resultado_cero_no_envenena_el_factor(app):
    """Guardar solo frutos/árbol crea un ResultadoCosecha con tn_ha_real=0.

    Ese cero NO es una cosecha: si contara, hundiría el factor. Regresión del
    hallazgo FUN-05 de la auditoría.
    """
    cid, ids = _campana(app, tn_ha_predicho=20.0)
    _cosechar(app, cid, ids[:3], tn_ha_real=24.0)
    with app.app_context():
        # Lote 4: fila creada por el muestreo pre-cosecha, aún sin rendimiento real.
        db.session.add(ResultadoCosecha(lote_id=ids[3], campana_id=cid,
                                        tn_ha_real=0, frutos_arbol=120))
        db.session.commit()
        r = factor_recalibracion(db.session.get(Campana, cid))
    assert r["n_lotes"] == 3                       # el de 0 no cuenta
    assert r["factor"] == pytest.approx(1.2, abs=1e-3)


# --------------------------------------------------------------------------- #
#  Efecto sobre el total de campaña (lo que consume el plan F4)
# --------------------------------------------------------------------------- #

def test_total_usa_real_donde_hay_y_recalibra_el_resto(app):
    """3 lotes reales a 26 + 3 pendientes recalibrados a 20×1.3 = 26. Total = 6×26×10."""
    cid, ids = _campana(app, n_lotes=6, area=10.0, tn_ha_predicho=20.0)
    _cosechar(app, cid, ids[:3], tn_ha_real=26.0)
    with app.app_context():
        t = total_campana(db.session.get(Campana, cid))

    assert t["recalibracion"]["aplicable"] is True
    assert t["tn_total_crudo"] == pytest.approx(6 * 20.0 * 10.0)   # sin corregir: 1200
    assert t["tn_total"] == pytest.approx(6 * 26.0 * 10.0)         # corregido: 1560

    fuentes = {f["fuente"] for f in t["por_lote"]}
    assert fuentes == {"real", "recalibrado"}
    assert sum(1 for f in t["por_lote"] if f["fuente"] == "real") == 3
    # El predicho crudo se conserva para poder auditar la corrección.
    assert all(f["tn_ha_predicho"] == 20.0 for f in t["por_lote"])


def test_total_sin_cosecha_es_el_crudo(app):
    """Sin evidencia, el total recalibrado coincide con el crudo (no inventa nada)."""
    cid, _ = _campana(app, n_lotes=4, area=5.0, tn_ha_predicho=20.0)
    with app.app_context():
        t = total_campana(db.session.get(Campana, cid))
    assert t["tn_total"] == pytest.approx(t["tn_total_crudo"])
    assert {f["fuente"] for f in t["por_lote"]} == {"predicho"}


def test_endpoint_recalibracion(app):
    cid, ids = _campana(app, tn_ha_predicho=20.0)
    client = app.test_client()

    d = client.get(f"/api/campanas/{cid}/recalibracion").get_json()
    assert d["aplicable"] is False

    _cosechar(app, cid, ids[:3], tn_ha_real=24.0)
    d = client.get(f"/api/campanas/{cid}/recalibracion").get_json()
    assert d["aplicable"] is True
    assert d["factor"] == pytest.approx(1.2, abs=1e-3)
    assert d["n_lotes"] == 3


def test_plan_de_cosecha_usa_el_total_recalibrado(app):
    """La cascada F4→F5 debe planificar sobre el nivel corregido, no sobre el del día 1."""
    cid, ids = _campana(app, n_lotes=6, area=10.0, tn_ha_predicho=20.0)
    _cosechar(app, cid, ids[:3], tn_ha_real=26.0)
    r = app.test_client().post(f"/api/campanas/{cid}/plan-cosecha",
                               json={"fecha_inicio": "2025-02-03", "semanas_total": 4})
    assert r.status_code == 201
    assert r.get_json()["tn_total"] == pytest.approx(1560.0, abs=1.0)


# --------------------------------------------------------------------------- #
#  Intervalo conformal
# --------------------------------------------------------------------------- #

def test_intervalo_declara_si_esta_calibrado(app):
    """El intervalo nunca puede presentarse como calibrado si no lo está."""
    from app.ml.predictor import Predictor

    p = Predictor(app.config["ML_MODEL_PATH"])
    iv = p._intervalo(20.0, None)
    conformal = bool((p.meta.get("conformal") or {}).get("q"))

    if conformal:
        assert iv["calibrado"] is True
        assert iv["cobertura"] is not None
        assert iv["p90"] - iv["p10"] > 0
        assert iv["p10"] >= 0                      # el rendimiento no es negativo
    else:
        # Sin bloque conformal y sin árboles no hay intervalo que ofrecer.
        assert iv is None


def _predictor_con_meta(tmp_path, bloque):
    """Predictor apuntado a un modelo_meta.json temporal (no toca el del repo)."""
    import json
    from app.ml.predictor import Predictor

    (tmp_path / "modelo_meta.json").write_text(
        json.dumps({"features": [], "rangos_entrenamiento": {}, "conformal": bloque}),
        encoding="utf-8")
    return Predictor(str(tmp_path / "modelo.pkl"))


def test_intervalo_conformal_es_simetrico_y_no_negativo(tmp_path):
    """Con margen q, el intervalo es tn_ha ± q, recortado en 0 por abajo."""
    p = _predictor_con_meta(tmp_path, {"q": 10.8, "cobertura": 0.80, "n": 30,
                                       "origen": "cosecha real"})
    iv = p._intervalo(20.0, None)
    assert iv["p10"] == pytest.approx(9.2)
    assert iv["p90"] == pytest.approx(30.8)
    assert iv["calibrado"] is True
    assert iv["cobertura"] == 0.80
    assert iv["origen"] == "cosecha real"
    assert iv["n_calibracion"] == 30

    # Predicción baja: el límite inferior se recorta en 0, no queda negativo.
    assert p._intervalo(5.0, None)["p10"] == 0.0


def test_meta_se_recarga_si_cambia_en_disco(tmp_path):
    """`calibrar.py` reescribe el margen; el proceso servidor debe tomarlo sin reiniciar."""
    import json
    import os

    p = _predictor_con_meta(tmp_path, {"q": 10.0, "cobertura": 0.80, "n": 10, "origen": "v1"})
    assert p._intervalo(20.0, None)["p90"] == pytest.approx(30.0)

    ruta = tmp_path / "modelo_meta.json"
    ruta.write_text(json.dumps({"conformal": {"q": 4.0, "cobertura": 0.80,
                                              "n": 40, "origen": "v2"}}), encoding="utf-8")
    os.utime(ruta, (0, 0))                       # mtime distinto, sin depender del reloj
    iv = p._intervalo(20.0, None)
    assert iv["p90"] == pytest.approx(24.0)
    assert iv["origen"] == "v2"
