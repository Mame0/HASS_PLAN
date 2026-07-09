"""Pruebas F7: resultado de cosecha (predicho vs real, MAE/MAPE, upsert, validación)."""
from datetime import date

from app.models import db, Finca, Lote, Campana, LoteCampana, RegistroAgronomico

NEPENA = {
    "edad_campo": 7, "edad_prod": 5, "riego_m3ha": 16000,
    "hfrio_19": 3559, "hfrio_14_19": 3471, "hfrio_14": 108, "hfrio_15": 389,
    "hac_20_25": 3523, "hac_25": 725, "humedad": 76, "eto": 1469,
    "t_min": 17.2, "t_max": 23.7, "t_prom": 19.9, "lluvia": 56.5,
}


def _campana_con_prediccion(app, n_lotes=2, area=5.0):
    """Crea una campaña activa con n lotes predichos. Devuelve (cid, [lote_ids])."""
    with app.app_context():
        f = Finca(nombre="Chacra")
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
            db.session.add(RegistroAgronomico(lote_id=lote.id, campana_id=c.id, **NEPENA))
            ids.append(lote.id)
        db.session.commit()
        cid = c.id
    client = app.test_client()
    for lid in ids:
        client.post(f"/api/lotes/{lid}/prediccion")
    return cid, ids


def test_guardar_y_comparar_predicho_vs_real(app):
    cid, ids = _campana_con_prediccion(app, n_lotes=2)
    client = app.test_client()

    # Registrar cosecha real solo del primer lote.
    r = client.put(f"/api/lotes/{ids[0]}/resultado?campana_id={cid}",
                   json={"tn_ha_real": 18.0, "frutos_arbol": 250, "peso_fruto": 210})
    assert r.status_code == 200
    assert r.get_json()["tn_ha_real"] == 18.0

    comp = client.get(f"/api/campanas/{cid}/resultados").get_json()
    assert comp["resumen"]["n_lotes"] == 2
    assert comp["resumen"]["n_con_real"] == 1
    assert comp["resumen"]["n_comparables"] == 1

    fila = next(x for x in comp["por_lote"] if x["lote_id"] == ids[0])
    assert fila["tn_ha_real"] == 18.0
    assert fila["tiene_prediccion"] is True
    # el error coincide con |real - predicho| calculado desde el propio predicho devuelto
    esperado = round(abs(18.0 - fila["tn_ha_predicho"]), 2)
    assert fila["error_abs"] == esperado
    assert comp["resumen"]["mae"] == esperado          # 1 solo comparable -> MAE = su error

    # el lote sin cosecha real no es comparable
    otro = next(x for x in comp["por_lote"] if x["lote_id"] == ids[1])
    assert otro["tn_ha_real"] is None
    assert otro["error_abs"] is None


def test_upsert_no_duplica(app):
    cid, ids = _campana_con_prediccion(app, n_lotes=1)
    client = app.test_client()
    client.put(f"/api/lotes/{ids[0]}/resultado?campana_id={cid}", json={"tn_ha_real": 15})
    client.put(f"/api/lotes/{ids[0]}/resultado?campana_id={cid}", json={"tn_ha_real": 20})
    comp = client.get(f"/api/campanas/{cid}/resultados").get_json()
    con_real = [x for x in comp["por_lote"] if x["tiene_real"]]
    assert len(con_real) == 1                 # se actualizó, no se duplicó
    assert con_real[0]["tn_ha_real"] == 20.0


def test_tn_real_debe_ser_positivo(app):
    cid, ids = _campana_con_prediccion(app, n_lotes=1)
    client = app.test_client()
    assert client.put(f"/api/lotes/{ids[0]}/resultado?campana_id={cid}",
                      json={"tn_ha_real": 0}).status_code == 400
    assert client.put(f"/api/lotes/{ids[0]}/resultado?campana_id={cid}",
                      json={"tn_ha_real": -5}).status_code == 400
    assert client.put(f"/api/lotes/{ids[0]}/resultado?campana_id={cid}",
                      json={}).status_code == 400


def test_borrar_resultado(app):
    cid, ids = _campana_con_prediccion(app, n_lotes=1)
    client = app.test_client()
    client.put(f"/api/lotes/{ids[0]}/resultado?campana_id={cid}", json={"tn_ha_real": 12})
    assert client.delete(f"/api/lotes/{ids[0]}/resultado?campana_id={cid}").status_code == 200
    comp = client.get(f"/api/campanas/{cid}/resultados").get_json()
    assert comp["resumen"]["n_con_real"] == 0
    assert all(not x["tiene_real"] for x in comp["por_lote"])
