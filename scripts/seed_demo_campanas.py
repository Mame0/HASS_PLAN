"""
Demo de LOTES POR CAMPAÑA (tabla puente LoteCampana) — para probar la función nueva.

Crea una finca aparte ("Fundo Demo Multicampaña", NO toca tus datos reales) con 4 lotes
físicos y 3 campañas, cada una con su PROPIO set de lotes, para que al cambiar de campaña
en la UI se vea cómo aumentan/disminuyen:

  · Demo 2023-24 (cerrada)  → lotes A, B, C        (+ registros + predicción; solo lectura)
  · Demo 2024-25 (borrador) → lotes B, C, D        (A se retiró, D es nuevo; B y C son los
                                                     MISMOS lotes físicos → historia continua)
  · Demo 2026-27 (futura)   → lotes B, D           (sync de clima dará 502 con mensaje claro)

No crea ninguna campaña "activa" para NO desplazar tu campaña activa real; selecciona las
campañas demo desde el selector de la cabecera.

Demuestra: (1) cada campaña ve solo sus lotes; (2) un lote agregado en una campaña no
aparece en otra; (3) la identidad del lote se conserva entre campañas; (4) clima futuro = 502.

Uso (desde sistema_palta/):
    python scripts/seed_demo_campanas.py            # crea la demo (no duplica)
    python scripts/seed_demo_campanas.py --reset    # la borra y recrea
"""
import os
import sys
import math
import json
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, Finca, Lote, Campana, LoteCampana, RegistroAgronomico
from app.services.geo import resumen
from app.services.prediccion import predecir_lote

FINCA_NOMBRE = "Fundo Demo Multicampaña"
BASE_LAT, BASE_LON = -16.592, -71.922

# Clima de La Joya (manual, para que la predicción funcione sin llamar a la API).
CLIMA_LAJOYA = {
    "hfrio_19": 4585, "hfrio_15": 1410, "hfrio_14": 520, "hfrio_14_19": 3680,
    "hac_20_25": 2037, "hac_25": 1519, "t_prom": 19.6, "t_min": 14.1, "t_max": 27.3,
    "humedad": 52, "lluvia": 10, "eto": 1880,
}

# 4 lotes físicos (A–D) con manejo distinto -> predicciones distintas.
LOTES = {
    "A": {"nombre": "Lote A — Norte",  "edad_campo": 8,  "edad_prod": 6,  "riego_m3ha": 14000, "lado_m": 180},
    "B": {"nombre": "Lote B — Centro", "edad_campo": 5,  "edad_prod": 3,  "riego_m3ha": 15200, "lado_m": 150},
    "C": {"nombre": "Lote C — Viejo",  "edad_campo": 12, "edad_prod": 10, "riego_m3ha": 13500, "lado_m": 220},
    "D": {"nombre": "Lote D — Nuevo",  "edad_campo": 3,  "edad_prod": 1,  "riego_m3ha": 16000, "lado_m": 130},
}

# Campañas: (nombre, inicio, fin, estado, [claves de lotes que participan])
CAMPANAS = [
    ("Demo 2023-24", date(2023, 7, 1), date(2024, 6, 30), "cerrada",  ["A", "B", "C"]),
    ("Demo 2024-25", date(2024, 7, 1), date(2025, 6, 30), "borrador", ["B", "C", "D"]),
    ("Demo 2026-27", date(2026, 9, 1), date(2027, 4, 30), "borrador", ["B", "D"]),
]


def cuadrado(lat0, lon0, lado_m):
    dlat = lado_m / 110574
    dlon = lado_m / (111320 * math.cos(math.radians(lat0)))
    return {"type": "Polygon", "coordinates": [[
        [lon0, lat0], [lon0 + dlon, lat0],
        [lon0 + dlon, lat0 + dlat], [lon0, lat0 + dlat], [lon0, lat0],
    ]]}


def _crear_campana(nombre, di, df, estado, claves, lotes, hoy):
    """Crea una campaña, asocia sus lotes y (si no es futura) su registro + predicción."""
    camp = Campana(nombre=nombre, fecha_inicio=di, fecha_fin=df, estado=estado)
    db.session.add(camp)
    db.session.flush()
    print(f"\n{nombre} ({estado}) → lotes: {', '.join(claves)}")
    es_pasada = di <= hoy
    for clave in claves:
        lote = lotes[clave]
        db.session.add(LoteCampana(lote_id=lote.id, campana_id=camp.id, en_produccion=True))
        if es_pasada:
            spec = LOTES[clave]
            db.session.add(RegistroAgronomico(
                lote_id=lote.id, campana_id=camp.id,
                edad_campo=spec["edad_campo"], edad_prod=spec["edad_prod"],
                riego_m3ha=spec["riego_m3ha"], **CLIMA_LAJOYA))
    db.session.commit()
    if not es_pasada:
        print("    (campaña futura: sin clima/predicción; el sync de clima dará 502)")
        return
    for clave in claves:
        pred, res = predecir_lote(lotes[clave], camp)
        ood = "  [OOD]" if res["es_extrapolacion"] else ""
        print(f"    {lotes[clave].nombre:<18} → {pred.tn_ha_predicho:>5.1f} Tn/Ha{ood}")


def _borrar_demo():
    """Borra la finca demo y TODA campaña cuyo nombre empiece por 'Demo ' (robusto ante
    renombres de campañas demo previas)."""
    for f in Finca.query.filter_by(nombre=FINCA_NOMBRE).all():
        db.session.delete(f)
    for c in Campana.query.filter(Campana.nombre.like("Demo %")).all():
        db.session.delete(c)
    db.session.commit()


def main(reset=False):
    app = create_app()
    with app.app_context():
        existe = Finca.query.filter_by(nombre=FINCA_NOMBRE).first()
        if existe and not reset:
            print("Ya existe la finca demo. Usa --reset para recrearla.")
            return
        if reset:
            _borrar_demo()

        finca = Finca(nombre=FINCA_NOMBRE, distrito="La Joya, Arequipa (DEMO)",
                      centro_lat=BASE_LAT, centro_lon=BASE_LON)
        db.session.add(finca)
        db.session.flush()

        # Crear los 4 lotes físicos
        lotes = {}
        for i, (clave, spec) in enumerate(LOTES.items()):
            geom = cuadrado(BASE_LAT + i * 0.003, BASE_LON + i * 0.003, spec["lado_m"])
            r = resumen(json.dumps(geom))
            lote = Lote(finca_id=finca.id, nombre=spec["nombre"], geometria=json.dumps(geom),
                        area_ha=r["area_ha"], latitud=r["centro_lat"], longitud=r["centro_lon"],
                        ano_plantacion=2024 - spec["edad_campo"])
            db.session.add(lote)
            db.session.flush()
            lotes[clave] = lote

        # Crear campañas + asociar sus lotes + (para las no-futuras) registro y predicción
        hoy = date.today()
        for nombre, di, df, estado, claves in CAMPANAS:
            _crear_campana(nombre, di, df, estado, claves, lotes, hoy)

        print(f"\nDemo lista: finca '{finca.nombre}' (#{finca.id}) con 4 lotes y 3 campañas.")
        print("Pruébalo:  python run.py  →  cambia de campaña en la cabecera y observa cómo")
        print("           el set de lotes cambia (A,B,C → B,C,D → B,D).")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)
