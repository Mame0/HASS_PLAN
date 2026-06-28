"""Pruebas F4: plan de cosecha (cuadre con el total, %=100, reprogramación)."""
from datetime import date

from app.models import db, Finca, Lote, Campana, LoteCampana, RegistroAgronomico

NEPENA = {
    "edad_campo": 7, "edad_prod": 5, "riego_m3ha": 16000,
    "hfrio_19": 3559, "hfrio_14_19": 3471, "hfrio_14": 108, "hfrio_15": 389,
    "hac_20_25": 3523, "hac_25": 725, "humedad": 76, "eto": 1469,
    "t_min": 17.2, "t_max": 23.7, "t_prom": 19.9, "lluvia": 56.5,
}


def _campana_con_prediccion(app, n_lotes=2, area=5.0):
    """Crea una campaña activa con n lotes predichos y devuelve su id."""
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
    return cid


def test_generar_plan_cuadra_con_total(app):
    cid = _campana_con_prediccion(app)
    r = app.test_client().post(f"/api/campanas/{cid}/plan-cosecha",
                               json={"fecha_inicio": "2026-01-05", "semanas_total": 12})
    assert r.status_code == 201
    plan = r.get_json()
    assert len(plan["semanas"]) == 12
    suma = round(sum(s["tn_planificada"] for s in plan["semanas"]), 2)
    assert abs(suma - plan["tn_total"]) < 0.05           # Σ semanas = tn_total
    assert abs(sum(s["porcentaje"] for s in plan["semanas"]) - 100) < 0.5   # Σ% ≈ 100


def test_plan_sin_prediccion_400(app):
    with app.app_context():
        f = Finca(nombre="Chacra")
        db.session.add(f)
        db.session.flush()
        c = Campana(nombre="x", finca_id=f.id, fecha_inicio=date(2024, 7, 1),
                    fecha_fin=date(2025, 6, 30), estado="activa")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    r = app.test_client().post(f"/api/campanas/{cid}/plan-cosecha",
                               json={"fecha_inicio": "2026-01-05", "semanas_total": 8})
    assert r.status_code == 400


def test_reprogramar_mantiene_total(app):
    cid = _campana_con_prediccion(app)
    c = app.test_client()
    plan = c.post(f"/api/campanas/{cid}/plan-cosecha",
                  json={"fecha_inicio": "2026-01-05", "semanas_total": 10}).get_json()
    total = plan["tn_total"]
    s1 = plan["semanas"][0]["id"]
    nuevo = round(total * 0.4, 2)
    plan2 = c.put(f"/api/semanas/{s1}", json={"tn_planificada": nuevo}).get_json()
    suma = round(sum(s["tn_planificada"] for s in plan2["semanas"]), 2)
    assert abs(suma - total) < 0.05                      # sigue cuadrando
    s1n = next(s for s in plan2["semanas"] if s["id"] == s1)
    assert abs(s1n["tn_planificada"] - nuevo) < 0.1      # la semana quedó en el valor pedido


def test_reprogramar_excede_total_400(app):
    cid = _campana_con_prediccion(app)
    c = app.test_client()
    plan = c.post(f"/api/campanas/{cid}/plan-cosecha",
                  json={"fecha_inicio": "2026-01-05", "semanas_total": 8}).get_json()
    s1 = plan["semanas"][0]["id"]
    r = c.put(f"/api/semanas/{s1}", json={"tn_planificada": plan["tn_total"] + 100})
    assert r.status_code == 400


def test_curvas_forma_y_cuadre(app):
    """Cada curva reparte distinto pero SIEMPRE cuadra con el total y suma 100%."""
    cid = _campana_con_prediccion(app)
    c = app.test_client()
    for curva in ("campana", "uniforme", "creciente", "decreciente"):
        plan = c.post(f"/api/campanas/{cid}/plan-cosecha",
                      json={"fecha_inicio": "2026-01-05", "semanas_total": 6,
                            "curva": curva}).get_json()
        assert plan["curva"] == curva
        tn = [s["tn_planificada"] for s in plan["semanas"]]
        assert abs(round(sum(tn), 2) - plan["tn_total"]) < 0.05       # cuadra
        assert abs(sum(s["porcentaje"] for s in plan["semanas"]) - 100) < 0.5
        if curva == "uniforme":
            assert max(tn) - min(tn) < 0.05                           # todas iguales
        elif curva == "creciente":
            assert tn[-1] > tn[0]                                     # pico al final
        elif curva == "decreciente":
            assert tn[0] > tn[-1]                                     # pico al inicio
        elif curva == "campana":
            assert tn[len(tn) // 2] > tn[0] and tn[len(tn) // 2] > tn[-1]  # pico al centro


def test_curva_invalida_400(app):
    cid = _campana_con_prediccion(app)
    r = app.test_client().post(f"/api/campanas/{cid}/plan-cosecha",
                               json={"fecha_inicio": "2026-01-05", "semanas_total": 6,
                                     "curva": "espiral"})
    assert r.status_code == 400


def test_cosecha_real_se_registra_y_no_altera_plan(app):
    """tn_real es un dato de resultado: se guarda en la semana y NO redistribuye el plan."""
    cid = _campana_con_prediccion(app)
    c = app.test_client()
    plan = c.post(f"/api/campanas/{cid}/plan-cosecha",
                  json={"fecha_inicio": "2026-01-05", "semanas_total": 8}).get_json()
    total = plan["tn_total"]
    s1 = plan["semanas"][0]["id"]
    plan2 = c.put(f"/api/semanas/{s1}/real", json={"tn_real": 3.5}).get_json()
    s1n = next(s for s in plan2["semanas"] if s["id"] == s1)
    assert s1n["tn_real"] == 3.5                                       # se registró
    suma = round(sum(s["tn_planificada"] for s in plan2["semanas"]), 2)
    assert abs(suma - total) < 0.05                                    # el plan no cambió
    # Borrar el registro (null) deja la semana "sin registrar".
    plan3 = c.put(f"/api/semanas/{s1}/real", json={"tn_real": None}).get_json()
    s1b = next(s for s in plan3["semanas"] if s["id"] == s1)
    assert s1b["tn_real"] is None


def test_cosecha_real_negativa_400(app):
    cid = _campana_con_prediccion(app)
    c = app.test_client()
    plan = c.post(f"/api/campanas/{cid}/plan-cosecha",
                  json={"fecha_inicio": "2026-01-05", "semanas_total": 6}).get_json()
    s1 = plan["semanas"][0]["id"]
    r = c.put(f"/api/semanas/{s1}/real", json={"tn_real": -1})
    assert r.status_code == 400
