"""Pruebas del Módulo 4: predicción, persistencia, bandera OOD y total de campaña."""
from datetime import date

from app.models import db, Finca, Lote, Campana, LoteCampana, RegistroAgronomico

# Valores de Nepeña 19-20 (dentro del rango de entrenamiento), en orden de FEATURES.
NEPENA = {
    "edad_campo": 7, "edad_prod": 5, "riego_m3ha": 16000,
    "hfrio_19": 3559, "hfrio_14_19": 3471, "hfrio_14": 108, "hfrio_15": 389,
    "hac_20_25": 3523, "hac_25": 725, "humedad": 76, "eto": 1469,
    "t_min": 17.2, "t_max": 23.7, "t_prom": 19.9, "lluvia": 56.5,
}
# La Joya: humedad y ETO fuera del rango de entrenamiento -> debe marcar extrapolación.
LAJOYA = {**NEPENA, "humedad": 52, "eto": 1880}


def _setup(app, valores, area_ha=5.0):
    with app.app_context():
        f = Finca(nombre="Chacra La Joya", distrito="La Joya")
        db.session.add(f)
        db.session.flush()
        c = Campana(nombre="24-25", finca_id=f.id, fecha_inicio=date(2024, 7, 1),
                    fecha_fin=date(2025, 6, 30), estado="activa")
        db.session.add(c)
        db.session.flush()
        lote = Lote(finca_id=f.id, nombre="L1", area_ha=area_ha)
        db.session.add(lote)
        db.session.flush()
        db.session.add(LoteCampana(lote_id=lote.id, campana_id=c.id, en_produccion=True))
        db.session.add(RegistroAgronomico(lote_id=lote.id, campana_id=c.id, **valores))
        db.session.commit()
        return lote.id, c.id


def test_predecir_persiste_relee_y_total(app):
    lid, cid = _setup(app, NEPENA, area_ha=5.0)
    client = app.test_client()

    r = client.post(f"/api/lotes/{lid}/prediccion")
    assert r.status_code == 200
    d = r.get_json()
    assert d["tn_ha"] > 0
    assert abs(d["tn_total"] - d["tn_ha"] * 5.0) < 0.5      # tn_total = tn_ha × área
    assert d["es_extrapolacion"] is False
    assert d["confianza"] is not None

    # se relee igual
    d2 = client.get(f"/api/lotes/{lid}/prediccion").get_json()
    assert d2["tn_ha"] == d["tn_ha"]

    # total de campaña = suma por lote
    t = client.get(f"/api/campanas/{cid}/prediccion").get_json()
    assert t["n_lotes"] == 1
    assert t["tn_total"] == d["tn_total"]


def test_bandera_ood_en_lajoya(app):
    lid, _ = _setup(app, LAJOYA)
    d = app.test_client().post(f"/api/lotes/{lid}/prediccion").get_json()
    assert d["es_extrapolacion"] is True
    fuera = {o["variable"] for o in d["out_of_distribution"]}
    assert "humedad" in fuera and "eto" in fuera


def test_predecir_sin_repetir_filas(app):
    """Re-predecir actualiza la misma fila (upsert), no crea duplicados."""
    lid, cid = _setup(app, NEPENA)
    client = app.test_client()
    client.post(f"/api/lotes/{lid}/prediccion")
    client.post(f"/api/lotes/{lid}/prediccion")
    with app.app_context():
        from app.models import Prediccion
        assert Prediccion.query.filter_by(lote_id=lid, campana_id=cid).count() == 1


def test_faltan_variables_devuelve_400(app):
    valores = {k: v for k, v in NEPENA.items() if k != "humedad"}
    lid, _ = _setup(app, valores)
    r = app.test_client().post(f"/api/lotes/{lid}/prediccion")
    assert r.status_code == 400
