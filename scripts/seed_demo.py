"""
Carga datos de EJEMPLO para probar el sistema sin front (Chacra La Joya).

Crea: 1 campaña activa + 1 finca con 4 lotes dibujados (polígonos), su registro
agronómico (3 manuales + 12 climáticas de La Joya), corre la predicción de cada lote
y genera el plan de cosecha. Tras correrlo, levanta el server y explora la API.

Uso:
    python scripts/seed_demo.py            # crea la demo (no duplica si ya existe)
    python scripts/seed_demo.py --reset    # borra la demo y la recrea
"""
import os
import sys
import math
import json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, Finca, Lote, Campana, RegistroAgronomico
from app.services.geo import resumen
from app.services.prediccion import predecir_lote
from app.services.planificacion import generar_plan_cosecha
from app.services.derivados import (
    configurar_mano_obra, configurar_transporte, set_inventario)
from app.services.alertas import generar_alertas

# Clima de La Joya (desierto) — varias variables caen FUERA del rango de Nepeña
# (humedad, ETO, t_min, t_max, hac_25, lluvia) -> la predicción saldrá marcada como
# extrapolación (OOD). Es el caso real: modelo entrenado en costa, desplegado en desierto.
CLIMA_LAJOYA = {
    "hfrio_19": 4585, "hfrio_15": 1410, "hfrio_14": 520, "hfrio_14_19": 3680,
    "hac_20_25": 2037, "hac_25": 1519, "t_prom": 19.6, "t_min": 14.1, "t_max": 27.3,
    "humedad": 52, "lluvia": 10, "eto": 1880,
}

# 4 lotes con manejo distinto (edad/riego) -> predicciones distintas
LOTES = [
    {"nombre": "Lote 1 — Norte",  "edad_campo": 8,  "edad_prod": 6,  "riego_m3ha": 14000, "lado_m": 180},
    {"nombre": "Lote 2 — Centro", "edad_campo": 5,  "edad_prod": 3,  "riego_m3ha": 15200, "lado_m": 150},
    {"nombre": "Lote 3 — Viejo",  "edad_campo": 12, "edad_prod": 10, "riego_m3ha": 13500, "lado_m": 220},
    {"nombre": "Lote 4 — Nuevo",  "edad_campo": 3,  "edad_prod": 1,  "riego_m3ha": 16000, "lado_m": 130},
]

BASE_LAT, BASE_LON = -16.592, -71.922   # Chacra en La Joya, Arequipa


def cuadrado(lat0, lon0, lado_m):
    """Polígono GeoJSON cuadrado de `lado_m` metros con esquina en (lat0, lon0)."""
    dlat = lado_m / 110574
    dlon = lado_m / (111320 * math.cos(math.radians(lat0)))
    return {"type": "Polygon", "coordinates": [[
        [lon0, lat0], [lon0 + dlon, lat0],
        [lon0 + dlon, lat0 + dlat], [lon0, lat0 + dlat], [lon0, lat0],
    ]]}


def _borrar_demo():
    for f in Finca.query.filter_by(nombre="Chacra La Joya").all():
        db.session.delete(f)
    for c in Campana.query.filter_by(nombre="Campaña 2024-25").all():
        db.session.delete(c)
    db.session.commit()


def main(reset=False):
    app = create_app()
    with app.app_context():
        existe = Finca.query.filter_by(nombre="Chacra La Joya").first()
        if existe and not reset:
            print("Ya existe la finca demo. Usa --reset para recrearla.")
            return
        if reset:
            _borrar_demo()

        camp = Campana(nombre="Campaña 2024-25", fecha_inicio=date(2024, 7, 1),
                       fecha_fin=date(2025, 6, 30), estado="activa")
        finca = Finca(nombre="Chacra La Joya", distrito="La Joya, Arequipa",
                      centro_lat=BASE_LAT, centro_lon=BASE_LON)
        db.session.add_all([camp, finca])
        db.session.flush()

        for i, spec in enumerate(LOTES):
            geom = cuadrado(BASE_LAT + i * 0.003, BASE_LON + i * 0.003, spec["lado_m"])
            r = resumen(json.dumps(geom))
            lote = Lote(finca_id=finca.id, nombre=spec["nombre"], geometria=json.dumps(geom),
                        area_ha=r["area_ha"], latitud=r["centro_lat"], longitud=r["centro_lon"],
                        ano_plantacion=2024 - spec["edad_campo"])
            db.session.add(lote)
            db.session.flush()
            db.session.add(RegistroAgronomico(
                lote_id=lote.id, campana_id=camp.id,
                edad_campo=spec["edad_campo"], edad_prod=spec["edad_prod"],
                riego_m3ha=spec["riego_m3ha"], **CLIMA_LAJOYA))
        db.session.commit()

        # Predecir cada lote y generar el plan de cosecha
        for lote in finca.lotes:
            pred, res = predecir_lote(lote, camp)
            ood = "  [extrapolacion OOD]" if res["es_extrapolacion"] else ""
            print(f"  {lote.nombre:<18} {lote.area_ha:>5.2f} ha  ->  {pred.tn_ha_predicho:>5.1f} Tn/Ha{ood}")

        # Cosecha realista de La Joya: feb–jun, ~16 semanas (ver docs/REFERENCIA_LA_JOYA.md)
        plan = generar_plan_cosecha(camp, date(2025, 2, 10), 16)

        # Módulos derivados (F5) con parámetros reales de La Joya, de modo que la demo
        # ya tenga déficits calculados para cuando F6 genere alertas.
        configurar_mano_obra(plan, rendimiento_jornal=0.10, tam_cuadrilla=6,
                             cuadrillas_disponibles=6, dias_cosecha_semana=6)
        configurar_transporte(plan, cap_camion_tn=3.5, costo_por_viaje=250,
                              camiones_disponibles=2, viajes_por_camion_semana=12)
        set_inventario(camp, [
            {"material": "jaba",   "cantidad_disponible": 1000, "unidad": "und", "consumo_por_tn": 45},
            {"material": "pallet", "cantidad_disponible": 2000, "unidad": "und", "consumo_por_tn": 1},
        ])
        generar_alertas(camp)   # deja las alertas de déficit listas para el panel (F6)

        print(f"\nDemo lista: finca '{finca.nombre}' (#{finca.id}), campaña #{camp.id}, "
              f"{len(finca.lotes)} lotes, predicciones, plan de cosecha de 16 semanas "
              f"y módulos M6/M7/M8 configurados (con déficits en el pico).")
        print("Levanta el server con:  python run.py")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)
