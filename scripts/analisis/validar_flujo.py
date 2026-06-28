"""
Validación end-to-end del flujo operativo (F1 → F4 → F5).

Recorre TODO el pipeline sobre una BD temporal y muestra los números en cada paso,
verificando las fórmulas de los módulos derivados con asserts. Sirve como evidencia
reproducible para la tesis: "así fluye un dato desde el lote hasta camiones y déficits".

    Predicción (ML) ──▶ Plan de Cosecha (curva semanal)
                          ├─▶ M6 Mano de obra  (jornales, cuadrillas, déficit)
                          ├─▶ M7 Logística     (materiales por semana, déficit)
                          └─▶ M8 Transporte    (viajes, camiones, costo, déficit)
    Reprogramar una semana ──▶ recalcula los tres módulos (cascada)

Uso:  python scripts/analisis/validar_flujo.py
"""
import math
import os
import sys
import tempfile
from datetime import date

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

# La consola de Windows usa cp1252; forzar UTF-8 para los símbolos del reporte.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from app import create_app                                              # noqa: E402
from app.models import db, Finca, Lote, Campana, RegistroAgronomico     # noqa: E402

# Lote tipo de Nepeña (campaña completa) — mismas cifras que usan los tests.
NEPENA = {
    "edad_campo": 7, "edad_prod": 5, "riego_m3ha": 16000,
    "hfrio_19": 3559, "hfrio_14_19": 3471, "hfrio_14": 108, "hfrio_15": 389,
    "hac_20_25": 3523, "hac_25": 725, "humedad": 76, "eto": 1469,
    "t_min": 17.2, "t_max": 23.7, "t_prom": 19.9, "lluvia": 56.5,
}

# Parámetros operativos REALES de La Joya (ver docs/REFERENCIA_LA_JOYA.md).
# Campaña feb–jun (~16 sem); jornal 0.10 t/día; camiones 3–4 t; jaba 45/t.
N_LOTES, AREA_HA, SEMANAS = 2, 6.0, 16
FECHA_INICIO = "2026-02-09"
MANO_OBRA = {"rendimiento_jornal": 0.10, "tam_cuadrilla": 6,
             "cuadrillas_disponibles": 6, "dias_cosecha_semana": 6}
TRANSPORTE = {"cap_camion_tn": 3.5, "costo_por_viaje": 250,
              "camiones_disponibles": 2, "viajes_por_camion_semana": 12}
INVENTARIO = [
    {"material": "jaba",   "cantidad_disponible": 1000, "unidad": "und", "consumo_por_tn": 45},
    {"material": "pallet", "cantidad_disponible": 2000, "unidad": "und", "consumo_por_tn": 1},
]


def _ceil(x):
    return int(math.ceil(round(x, 6)))


def h(titulo):
    print("\n" + "═" * 72 + f"\n  {titulo}\n" + "═" * 72)


def main():
    tmp = tempfile.mkdtemp()

    class Cfg:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(tmp, 'flujo.db')}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SECRET_KEY = "validar-flujo"
        ML_MODEL_PATH = os.path.join(RAIZ, "app", "ml", "modelo.pkl")

    app = create_app(Cfg)

    # ---- Semilla: finca + lotes + registros agronómicos -------------------
    with app.app_context():
        camp = Campana(nombre="24-25", fecha_inicio=date(2024, 7, 1),
                       fecha_fin=date(2025, 6, 30), estado="activa")
        finca = Finca(nombre="Chacra La Joya", distrito="La Joya, Arequipa")
        db.session.add_all([camp, finca])
        db.session.flush()
        lote_ids = []
        for i in range(N_LOTES):
            lote = Lote(finca_id=finca.id, nombre=f"Lote {i+1}", area_ha=AREA_HA)
            db.session.add(lote)
            db.session.flush()
            db.session.add(RegistroAgronomico(lote_id=lote.id, campana_id=camp.id, **NEPENA))
            lote_ids.append(lote.id)
        db.session.commit()
        cid = camp.id

    c = app.test_client()

    h("PASO 1 · Registro  →  Finca / Lotes / Campaña")
    print(f"  Finca: 'Chacra La Joya'  ·  {N_LOTES} lotes × {AREA_HA} ha  ·  campaña 24-25 (activa)")

    # ---- F1: predicción por lote -----------------------------------------
    h("PASO 2 · F1 Predicción ML por lote")
    tn_total_pred = 0.0
    for lid in lote_ids:
        r = c.post(f"/api/lotes/{lid}/prediccion").get_json()
        tn_total_pred += r["tn_total"]
        ood = " ⚠ extrapola" if r.get("es_extrapolacion") else ""
        print(f"  Lote {lid}: {r['tn_ha']:.2f} Tn/ha × {AREA_HA} ha = {r['tn_total']:.2f} Tn"
              f"  (confianza {r['confianza']}%){ood}")
    print(f"  ── Σ campaña ≈ {tn_total_pred:.2f} Tn")

    # ---- F4: plan de cosecha ---------------------------------------------
    h("PASO 3 · F4 Plan de Cosecha (curva semanal)")
    plan = c.post(f"/api/campanas/{cid}/plan-cosecha",
                  json={"fecha_inicio": FECHA_INICIO, "semanas_total": SEMANAS}).get_json()
    print(f"  {plan['semanas_total']} semanas · tn_total = {plan['tn_total']:.2f} Tn")
    print(f"  {'Sem':>3} {'Tn':>8} {'%':>7}")
    for s in plan["semanas"]:
        print(f"  {s['numero_semana']:>3} {s['tn_planificada']:>8.2f} {s['porcentaje']:>6.2f}%")
    suma = round(sum(s["tn_planificada"] for s in plan["semanas"]), 2)
    assert abs(suma - plan["tn_total"]) < 0.05, "Σ semanas ≠ tn_total"
    print(f"  ✓ cuadre: Σ semanas = {suma:.2f} = tn_total · Σ% = {sum(s['porcentaje'] for s in plan['semanas']):.1f}")

    # ---- F5 · M6 Mano de obra --------------------------------------------
    h("PASO 4 · F5/M6 Mano de Obra")
    p = MANO_OBRA
    print(f"  Parámetros: rendimiento={p['rendimiento_jornal']} Tn/jornal·día · "
          f"cuadrilla={p['tam_cuadrilla']} pers · {p['dias_cosecha_semana']} días/sem · "
          f"disponibles={p['cuadrillas_disponibles']} cuad")
    print("  Fórmula: jornales = tn/rendimiento ; cuadrillas = ceil(jornales/(tam·días))")
    mo = c.put(f"/api/campanas/{cid}/mano-obra", json=p).get_json()
    print(f"  {'Sem':>3} {'Tn':>7} {'Jornales':>9} {'Cuadr':>6} {'Déficit':>8}")
    for s in mo["semanas"]:
        jor = s["tn_planificada"] / p["rendimiento_jornal"]
        cua = _ceil(jor / (p["tam_cuadrilla"] * p["dias_cosecha_semana"]))
        assert s["cuadrillas_req"] == cua and abs(s["jornales_req"] - round(jor, 2)) < 0.01
        assert s["deficit"] == max(0, cua - p["cuadrillas_disponibles"])
        flag = " ⚠" if s["deficit"] > 0 else ""
        print(f"  {s['numero_semana']:>3} {s['tn_planificada']:>7.2f} {s['jornales_req']:>9.2f}"
              f" {s['cuadrillas_req']:>6} {s['deficit']:>8}{flag}")
    print(f"  ✓ fórmulas M6 verificadas · ¿déficit? {mo['tiene_deficit']}")

    # ---- F5 · M8 Transporte ----------------------------------------------
    h("PASO 5 · F5/M8 Transporte")
    p = TRANSPORTE
    print(f"  Parámetros: cap={p['cap_camion_tn']} Tn/camión · costo={p['costo_por_viaje']}/viaje · "
          f"{p['viajes_por_camion_semana']} viajes/camión·sem · flota={p['camiones_disponibles']}")
    print("  Fórmula: viajes = ceil(tn/cap) ; camiones = ceil(viajes/viajes_camión)")
    tr = c.put(f"/api/campanas/{cid}/transporte", json=p).get_json()
    print(f"  {'Sem':>3} {'Tn':>7} {'Viajes':>7} {'Camiones':>9} {'Costo':>9} {'Déficit':>8}")
    for s in tr["semanas"]:
        via = _ceil(s["tn_despachadas"] / p["cap_camion_tn"]) if s["tn_despachadas"] > 0 else 0
        cam = _ceil(via / p["viajes_por_camion_semana"]) if via > 0 else 0
        assert s["viajes"] == via and s["camiones"] == cam
        assert abs(s["costo"] - round(via * p["costo_por_viaje"], 2)) < 0.01
        flag = " ⚠" if s["deficit"] > 0 else ""
        print(f"  {s['numero_semana']:>3} {s['tn_despachadas']:>7.2f} {s['viajes']:>7}"
              f" {s['camiones']:>9} {s['costo']:>9.0f} {s['deficit']:>8}{flag}")
    print(f"  ✓ fórmulas M8 verificadas · costo_total = {tr['costo_total']:.0f} · ¿déficit? {tr['tiene_deficit']}")

    # ---- F5 · M7 Logística -----------------------------------------------
    h("PASO 6 · F5/M7 Logística / Inventario")
    print("  Inventario disponible: " + " · ".join(
        f"{i['material']} {i['cantidad_disponible']:.0f} ({i['consumo_por_tn']:.0f}/Tn)" for i in INVENTARIO))
    print("  Fórmula: requerido = tn × consumo/Tn ; déficit = max(0, requerido − stock)  [pico semanal]")
    c.put(f"/api/campanas/{cid}/inventario", json={"items": INVENTARIO})
    log = c.get(f"/api/campanas/{cid}/logistica").get_json()
    print(f"  {'Sem':>3} {'Tn':>7}   " + "  ".join(f"{i['material']:>16}" for i in INVENTARIO))
    for s in log["semanas"]:
        celdas = []
        for inv in INVENTARIO:
            m = next(x for x in s["materiales"] if x["material"] == inv["material"])
            req = round(s["tn_planificada"] * inv["consumo_por_tn"], 2)
            assert abs(m["cantidad_requerida"] - req) < 0.01
            assert abs(m["deficit"] - max(0.0, req - inv["cantidad_disponible"])) < 0.01
            txt = f"{m['cantidad_requerida']:>8.0f}" + (f"/-{m['deficit']:.0f}⚠" if m["deficit"] > 0 else "      ")
            celdas.append(f"{txt:>16}")
        print(f"  {s['numero_semana']:>3} {s['tn_planificada']:>7.2f}   " + "  ".join(celdas))
    print(f"  ✓ fórmulas M7 verificadas · ¿déficit? {log['tiene_deficit']}")

    # ---- Cascada: reprogramar una semana ---------------------------------
    h("PASO 7 · Cascada — reprogramar Semana 1 al 45% del total")
    s1 = plan["semanas"][0]
    nuevo = round(plan["tn_total"] * 0.45, 2)
    antes_mo = next(s for s in mo["semanas"] if s["semana_id"] == s1["id"])
    c.put(f"/api/semanas/{s1['id']}", json={"tn_planificada": nuevo})
    mo2 = c.get(f"/api/campanas/{cid}/mano-obra").get_json()
    tr2 = c.get(f"/api/campanas/{cid}/transporte").get_json()
    log2 = c.get(f"/api/campanas/{cid}/logistica").get_json()
    d_mo = next(s for s in mo2["semanas"] if s["semana_id"] == s1["id"])
    d_tr = next(s for s in tr2["semanas"] if s["semana_id"] == s1["id"])
    d_lo = next(s for s in log2["semanas"] if s["semana_id"] == s1["id"])
    jaba = next(m for m in d_lo["materiales"] if m["material"] == "jaba")
    print(f"  Semana 1:  {s1['tn_planificada']:.2f} Tn  →  {d_mo['tn_planificada']:.2f} Tn  (≈{nuevo})")
    print(f"    M6 cuadrillas: {antes_mo['cuadrillas_req']} → {d_mo['cuadrillas_req']}  "
          f"(déficit {antes_mo['deficit']} → {d_mo['deficit']})")
    print(f"    M8 viajes:     {d_tr['viajes']}  · camiones {d_tr['camiones']}  · déficit {d_tr['deficit']}")
    print(f"    M7 jaba req:   {jaba['cantidad_requerida']:.0f}  · déficit {jaba['deficit']:.0f}")
    suma2 = round(sum(s["tn_planificada"] for s in c.get(f"/api/campanas/{cid}/plan-cosecha").get_json()["semanas"]), 2)
    assert abs(suma2 - plan["tn_total"]) < 0.05, "tras reprogramar Σ ≠ tn_total"
    assert abs(d_mo["tn_planificada"] - nuevo) < 0.2, "la cascada no propagó"
    print(f"  ✓ cascada propagó a M6/M7/M8 · Σ sigue cuadrando = {suma2:.2f}")

    h("RESULTADO")
    print("  ✓ Flujo completo F1 → F4 → F5 verificado de punta a punta.")
    print("  ✓ Todas las fórmulas (M6/M7/M8) cuadran con el cálculo manual.")
    print("  ✓ La reprogramación de cosecha propaga a los tres módulos derivados.\n")


if __name__ == "__main__":
    main()
