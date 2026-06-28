"""
Pruebas F6: alertas (una por semana con déficit) + dashboard consolidado.

Gate:
  - cada déficit (personal/material/transporte) genera su alerta, ligada a la semana
  - severidad coherente con la magnitud del déficit
  - (re)generar es idempotente · resolver cambia el estado
  - el dashboard integra KPIs de todos los módulos + badge de alertas activas
"""
from datetime import date

from app.models import db, Finca, Lote, Campana, LoteCampana, RegistroAgronomico
from app.services.alertas import _severidad

NEPENA = {
    "edad_campo": 7, "edad_prod": 5, "riego_m3ha": 16000,
    "hfrio_19": 3559, "hfrio_14_19": 3471, "hfrio_14": 108, "hfrio_15": 389,
    "hac_20_25": 3523, "hac_25": 725, "humedad": 76, "eto": 1469,
    "t_min": 17.2, "t_max": 23.7, "t_prom": 19.9, "lluvia": 56.5,
}


def _montar(app, *, escasez=True, semanas=8):
    """Campaña activa con 2 lotes predichos + plan + M6/M7/M8. Devuelve (cid, client)."""
    with app.app_context():
        f = Finca(nombre="Chacra")
        db.session.add(f)
        db.session.flush()
        c = Campana(nombre="24-25", finca_id=f.id, fecha_inicio=date(2024, 7, 1),
                    fecha_fin=date(2025, 6, 30), estado="activa")
        db.session.add(c)
        db.session.flush()
        ids = []
        for i in range(2):
            lote = Lote(finca_id=f.id, nombre=f"L{i}", area_ha=5.0)
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
    client.post(f"/api/campanas/{cid}/plan-cosecha",
                json={"fecha_inicio": "2026-02-09", "semanas_total": semanas})
    # Recursos: escasos -> generan déficit ; holgados -> sin déficit
    cuad = 0 if escasez else 999
    cami = 0 if escasez else 999
    jaba_stock = 10 if escasez else 10_000_000
    client.put(f"/api/campanas/{cid}/mano-obra",
               json={"rendimiento_jornal": 0.10, "tam_cuadrilla": 6, "cuadrillas_disponibles": cuad})
    client.put(f"/api/campanas/{cid}/transporte",
               json={"cap_camion_tn": 3.5, "costo_por_viaje": 250, "camiones_disponibles": cami})
    client.put(f"/api/campanas/{cid}/inventario",
               json={"items": [{"material": "jaba", "cantidad_disponible": jaba_stock, "consumo_por_tn": 45}]})
    return cid, client


# --------------------------- severidad (unidad) ---------------------------

def test_severidad_umbrales():
    assert _severidad(1, 10) == "baja"     # 0.10
    assert _severidad(3, 10) == "media"    # 0.30
    assert _severidad(6, 10) == "alta"     # 0.60
    assert _severidad(5, 0) == "media"     # requerido 0 -> default seguro


# --------------------------- generación ---------------------------

def test_generar_alertas_por_semana_y_tipo(app):
    cid, client = _montar(app, escasez=True)
    r = client.post(f"/api/campanas/{cid}/alertas/generar")
    assert r.status_code == 201
    alertas = r.get_json()
    assert len(alertas) > 0
    tipos = {a["tipo"] for a in alertas}
    assert tipos == {"deficit_personal", "deficit_material", "deficit_transporte"}
    # cada alerta cuelga de una semana y trae mensaje
    assert all(a["semana_id"] is not None and a["mensaje"] for a in alertas)
    # con 0 disponibles, el déficit de personal es total -> severidad alta
    personal = [a for a in alertas if a["tipo"] == "deficit_personal"]
    assert all(a["severidad"] == "alta" for a in personal)


def test_idempotencia_no_duplica(app):
    cid, client = _montar(app, escasez=True)
    n1 = len(client.post(f"/api/campanas/{cid}/alertas/generar").get_json())
    n2 = len(client.post(f"/api/campanas/{cid}/alertas/generar").get_json())
    assert n1 == n2
    # listar todas debe dar el mismo número (no se acumularon)
    todas = client.get(f"/api/campanas/{cid}/alertas").get_json()
    assert len(todas) == n2


def test_sin_deficit_sin_alertas(app):
    cid, client = _montar(app, escasez=False)
    alertas = client.post(f"/api/campanas/{cid}/alertas/generar").get_json()
    assert alertas == []
    dash = client.get(f"/api/campanas/{cid}/dashboard").get_json()
    assert dash["alertas"]["activas"] == 0


# --------------------------- resolver ---------------------------

def test_resolver_alerta(app):
    cid, client = _montar(app, escasez=True)
    alertas = client.post(f"/api/campanas/{cid}/alertas/generar").get_json()
    aid = alertas[0]["id"]
    r = client.put(f"/api/alertas/{aid}", json={"estado": "resuelta"})
    assert r.status_code == 200 and r.get_json()["estado"] == "resuelta"
    activas = client.get(f"/api/campanas/{cid}/alertas?estado=activa").get_json()
    assert all(a["id"] != aid for a in activas)


# --------------------------- dashboard ---------------------------

def test_dashboard_integra_kpis(app):
    cid, client = _montar(app, escasez=True)
    client.post(f"/api/campanas/{cid}/alertas/generar")
    d = client.get(f"/api/campanas/{cid}/dashboard").get_json()
    assert d["prediccion"]["tn_total"] > 0 and d["prediccion"]["n_lotes"] == 2
    assert d["cosecha"]["tn_pico"] > 0 and d["cosecha"]["semana_pico"]
    assert d["mano_obra"]["cuadrillas_pico"] > 0 and d["mano_obra"]["tiene_deficit"] is True
    assert d["transporte"]["costo_total"] > 0
    assert d["logistica"]["tiene_deficit"] is True
    # badge: hay alertas activas y la suma por severidad cuadra con el total
    assert d["alertas"]["activas"] > 0
    assert sum(d["alertas"]["por_severidad"].values()) == d["alertas"]["activas"]
