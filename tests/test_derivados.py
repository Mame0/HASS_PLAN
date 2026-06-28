"""
Pruebas F5: módulos derivados (mano de obra, logística, transporte) y la cascada.

Verifica el gate:
  - fórmulas correctas (jornales, cuadrillas, viajes, camiones, costos, materiales)
  - déficits detectados (disponible vs requerido)
  - reprogramar la cosecha propaga a los tres módulos
"""
import math
from datetime import date

from app.models import db, Finca, Lote, Campana, LoteCampana, RegistroAgronomico

NEPENA = {
    "edad_campo": 7, "edad_prod": 5, "riego_m3ha": 16000,
    "hfrio_19": 3559, "hfrio_14_19": 3471, "hfrio_14": 108, "hfrio_15": 389,
    "hac_20_25": 3523, "hac_25": 725, "humedad": 76, "eto": 1469,
    "t_min": 17.2, "t_max": 23.7, "t_prom": 19.9, "lluvia": 56.5,
}


def _campana_con_plan(app, n_lotes=2, area=5.0, semanas=10):
    """Crea campaña + lotes predichos + plan de cosecha. Devuelve (cid, client, plan_json)."""
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
    plan = client.post(f"/api/campanas/{cid}/plan-cosecha",
                       json={"fecha_inicio": "2026-01-05", "semanas_total": semanas}).get_json()
    return cid, client, plan


def _ceil(x):
    return int(math.ceil(round(x, 6)))


# --------------------------- M6 Mano de obra ---------------------------

def test_mano_obra_formula_y_cuadre(app):
    cid, client, _ = _campana_con_plan(app)
    params = {"rendimiento_jornal": 0.5, "tam_cuadrilla": 10,
              "cuadrillas_disponibles": 5, "dias_cosecha_semana": 6}
    r = client.put(f"/api/campanas/{cid}/mano-obra", json=params)
    assert r.status_code == 200
    mo = r.get_json()
    assert len(mo["semanas"]) == 10
    for s in mo["semanas"]:
        jornales = s["tn_planificada"] / params["rendimiento_jornal"]
        cuadrillas = _ceil(jornales / (params["tam_cuadrilla"] * params["dias_cosecha_semana"]))
        assert abs(s["jornales_req"] - round(jornales, 2)) < 0.01
        assert s["cuadrillas_req"] == cuadrillas
        assert s["deficit"] == max(0, cuadrillas - params["cuadrillas_disponibles"])


def test_mano_obra_detecta_deficit(app):
    cid, client, _ = _campana_con_plan(app)
    # rendimiento bajo + 0 cuadrillas disponibles -> debe haber déficit en la semana pico
    mo = client.put(f"/api/campanas/{cid}/mano-obra",
                    json={"rendimiento_jornal": 0.3, "tam_cuadrilla": 8,
                          "cuadrillas_disponibles": 0, "dias_cosecha_semana": 6}).get_json()
    assert mo["tiene_deficit"] is True
    assert any(s["deficit"] > 0 for s in mo["semanas"])


def test_mano_obra_sin_plan_cosecha_400(app):
    with app.app_context():
        f = Finca(nombre="Chacra")
        db.session.add(f)
        db.session.flush()
        c = Campana(nombre="x", finca_id=f.id, fecha_inicio=date(2024, 7, 1),
                    fecha_fin=date(2025, 6, 30), estado="activa")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    r = app.test_client().put(f"/api/campanas/{cid}/mano-obra",
                              json={"rendimiento_jornal": 0.5, "tam_cuadrilla": 10})
    assert r.status_code == 400


def test_mano_obra_param_invalido_400(app):
    cid, client, _ = _campana_con_plan(app)
    r = client.put(f"/api/campanas/{cid}/mano-obra",
                   json={"rendimiento_jornal": 0, "tam_cuadrilla": 10})
    assert r.status_code == 400


# --------------------------- M8 Transporte ---------------------------

def test_transporte_formula_y_costo(app):
    cid, client, _ = _campana_con_plan(app)
    params = {"cap_camion_tn": 10, "costo_por_viaje": 800,
              "camiones_disponibles": 1, "viajes_por_camion_semana": 3}
    r = client.put(f"/api/campanas/{cid}/transporte", json=params)
    assert r.status_code == 200
    tr = r.get_json()
    costo_acum = 0
    for s in tr["semanas"]:
        viajes = _ceil(s["tn_despachadas"] / params["cap_camion_tn"]) if s["tn_despachadas"] > 0 else 0
        camiones = _ceil(viajes / params["viajes_por_camion_semana"]) if viajes > 0 else 0
        assert s["viajes"] == viajes
        assert s["camiones"] == camiones
        assert abs(s["costo"] - round(viajes * params["costo_por_viaje"], 2)) < 0.01
        assert s["deficit"] == max(0, camiones - params["camiones_disponibles"])
        costo_acum += s["costo"]
    assert abs(tr["costo_total"] - round(costo_acum, 2)) < 0.05


# --------------------------- M7 Logística / inventario ---------------------------

def test_inventario_logistica_deficit(app):
    cid, client, _ = _campana_con_plan(app)
    # jaba: consumo alto y stock bajo -> déficit en la semana pico; pallet: stock holgado
    items = {"items": [
        {"material": "jaba", "cantidad_disponible": 50, "unidad": "und", "consumo_por_tn": 100},
        {"material": "pallet", "cantidad_disponible": 100000, "unidad": "und", "consumo_por_tn": 2},
    ]}
    r = client.put(f"/api/campanas/{cid}/inventario", json=items)
    assert r.status_code == 200

    log = client.get(f"/api/campanas/{cid}/logistica").get_json()
    assert log["tiene_deficit"] is True
    for s in log["semanas"]:
        jaba = next(m for m in s["materiales"] if m["material"] == "jaba")
        assert abs(jaba["cantidad_requerida"] - round(s["tn_planificada"] * 100, 2)) < 0.01
        assert abs(jaba["deficit"] - max(0.0, jaba["cantidad_requerida"] - 50)) < 0.01
        pallet = next(m for m in s["materiales"] if m["material"] == "pallet")
        assert pallet["deficit"] == 0      # stock holgado, sin déficit


def test_inventario_negativo_400(app):
    cid, client, _ = _campana_con_plan(app)
    r = client.put(f"/api/campanas/{cid}/inventario",
                   json={"items": [{"material": "jaba", "cantidad_disponible": -5,
                                    "consumo_por_tn": 10}]})
    assert r.status_code == 400


# --------------------------- Cascada ---------------------------

def test_reprogramar_propaga_a_los_tres_modulos(app):
    cid, client, plan = _campana_con_plan(app, semanas=8)
    client.put(f"/api/campanas/{cid}/mano-obra",
               json={"rendimiento_jornal": 0.5, "tam_cuadrilla": 10, "cuadrillas_disponibles": 3})
    client.put(f"/api/campanas/{cid}/transporte",
               json={"cap_camion_tn": 10, "costo_por_viaje": 800, "camiones_disponibles": 1})
    client.put(f"/api/campanas/{cid}/inventario",
               json={"items": [{"material": "jaba", "cantidad_disponible": 50, "consumo_por_tn": 100}]})

    # Reprogramar la semana 1 al 50% del total
    total = plan["tn_total"]
    s1 = plan["semanas"][0]["id"]
    nuevo = round(total * 0.5, 2)
    client.put(f"/api/semanas/{s1}", json={"tn_planificada": nuevo})

    # Los tres módulos deben reflejar el nuevo tonelaje de la semana 1 (≈50% del total;
    # el cuadre de cosecha puede desplazarlo ±0.01, por eso se compara con el tn reportado).
    mo = client.get(f"/api/campanas/{cid}/mano-obra").get_json()
    mo_s1 = next(s for s in mo["semanas"] if s["semana_id"] == s1)
    assert abs(mo_s1["tn_planificada"] - nuevo) < 0.2                       # propagó el cambio
    assert abs(mo_s1["jornales_req"] - round(mo_s1["tn_planificada"] / 0.5, 2)) < 0.1

    tr = client.get(f"/api/campanas/{cid}/transporte").get_json()
    tr_s1 = next(s for s in tr["semanas"] if s["semana_id"] == s1)
    assert abs(tr_s1["tn_despachadas"] - nuevo) < 0.2
    assert tr_s1["viajes"] == _ceil(tr_s1["tn_despachadas"] / 10)

    log = client.get(f"/api/campanas/{cid}/logistica").get_json()
    log_s1 = next(s for s in log["semanas"] if s["semana_id"] == s1)
    jaba = next(m for m in log_s1["materiales"] if m["material"] == "jaba")
    assert abs(jaba["cantidad_requerida"] - round(log_s1["tn_planificada"] * 100, 2)) < 0.1
