"""
Z2 (parte 2): arma el panel zona x campana que consumira Z3 y mide lo que la serie permite medir.

Junta:
  * el clima por zona          (datos/zonas/clima_zonas.csv, 26 campanas)   <- Z1
  * el rendimiento de MIDAGRI  (datos/zonas/rendimiento_midagri.csv)        <- Z2
  * los controles no climaticos: crecimiento de la superficie cosechada (huertos jovenes bajan
    el promedio) y el rendimiento del ano anterior (veceria del palto).

LIMITACION QUE DEFINE EL ALCANCE
--------------------------------
MIDAGRI publica palta **solo por region**: La Joya y Majes comparten el mismo objetivo, y la
serie descargable es 2016-2023 (8 campanas). Por eso este script NO ajusta modelos: con n=8 y un
objetivo compartido, el efecto de zona no es identificable. Deja el panel armado y reporta
correlaciones descriptivas, con su intervalo, para que Z3 decida la unidad de analisis.

Salidas
-------
    datos/zonas/panel_zonas.csv    una fila por (zona, campana) con clima + objetivo + controles
    datos/zonas/panel_z2.json      cobertura, correlaciones y avisos

Uso (desde sistema_palta/)
--------------------------
    python scripts/zonas/panel_z2.py
    python scripts/zonas/panel_z2.py --region Arequipa
"""
import sys
import os
import json
import argparse
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")          # consola Windows cp1252 (ver CLAUDE.md)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

import pandas as pd                                                      # noqa: E402
from scipy import stats                                                  # noqa: E402

CLIMA = os.path.join(RAIZ, "datos", "zonas", "clima_zonas.csv")
RENDIMIENTO = os.path.join(RAIZ, "datos", "zonas", "rendimiento_midagri.csv")
SALIDA_CSV = os.path.join(RAIZ, "datos", "zonas", "panel_zonas.csv")
SALIDA_JSON = os.path.join(RAIZ, "datos", "zonas", "panel_z2.json")

FEATURES = ["hfrio_19", "hfrio_15", "hfrio_14", "hfrio_14_19", "hac_20_25", "hac_25",
            "t_prom", "t_min", "t_max", "humedad", "lluvia", "eto"]


def main():
    ap = argparse.ArgumentParser(description="Panel zona x campana con clima, objetivo y controles (Z2).")
    ap.add_argument("--region", default="Arequipa", help="region MIDAGRI que aporta el objetivo")
    args = ap.parse_args()

    for ruta, quien in ((CLIMA, "scripts/zonas/clima_zonas.py"),
                        (RENDIMIENTO, "scripts/zonas/rendimiento_midagri.py")):
        if not os.path.exists(ruta):
            print(f"Falta {os.path.relpath(ruta, RAIZ)}. Corre antes: python {quien}")
            return 1

    clima = pd.read_csv(CLIMA)
    rend = pd.read_csv(RENDIMIENTO)
    objetivo = rend[rend["region"].str.lower() == args.region.lower()].copy()
    if objetivo.empty:
        print(f"Sin datos de {args.region} en {os.path.relpath(RENDIMIENTO, RAIZ)}.")
        return 1

    # Controles no climaticos, en la serie del objetivo (no por zona: el objetivo es compartido)
    objetivo = objetivo.sort_values("anio")
    objetivo["var_superficie_pct"] = objetivo["superficie_cosechada_ha"].pct_change() * 100
    objetivo["rendimiento_anterior_t_ha"] = objetivo["rendimiento_t_ha"].shift(1)

    panel = clima.merge(
        objetivo[["anio", "rendimiento_t_ha", "superficie_cosechada_ha", "produccion_t",
                  "var_superficie_pct", "rendimiento_anterior_t_ha"]],
        on="anio", how="left")
    panel["region_objetivo"] = args.region
    panel["objetivo_compartido"] = True            # MIDAGRI no separa La Joya de Majes
    panel.to_csv(SALIDA_CSV, index=False, encoding="utf-8")

    con_objetivo = panel.dropna(subset=["rendimiento_t_ha"])
    anios = sorted(con_objetivo["anio"].unique())
    zonas = sorted(panel["zona"].unique())
    print(f"Panel: {len(panel)} filas ({len(zonas)} zonas x {panel['anio'].nunique()} campanas de clima)")
    print(f"Con objetivo ({args.region}): {len(con_objetivo)} filas · campanas {anios[0]}-{anios[-1]} "
          f"(n={len(anios)} por zona)")

    # Correlaciones descriptivas por zona: con n=8 solo sirven para ordenar sospechas
    print(f"\nCorrelacion clima-rendimiento por zona (n={len(anios)} campanas; "
          f"|r| necesita ~0.71 para p<0.05):")
    print(f"  {'variable':<14}" + "".join(f"{z[:10]:>22}" for z in zonas))
    resultados = {}
    for feat in FEATURES:
        fila = f"  {feat:<14}"
        resultados[feat] = {}
        for z in zonas:
            sub = con_objetivo[con_objetivo["zona"] == z]
            x, y = sub[feat], sub["rendimiento_t_ha"]
            if len(sub) >= 3 and x.notna().all():
                r, p = stats.pearsonr(x, y)
                rho, _ = stats.spearmanr(x, y)
                resultados[feat][z] = {"r": round(float(r), 3), "p": round(float(p), 4),
                                       "rho": round(float(rho), 3), "n": len(sub)}
                marca = "*" if p < 0.05 else " "
                fila += f"{r:>+12.2f} (p={p:.2f}){marca}"
            else:
                fila += f"{'sin datos':>22}"
        print(fila)

    # Los controles no climaticos, sobre la misma serie
    serie = objetivo.dropna(subset=["rendimiento_t_ha"])
    controles = {}
    for control in ("var_superficie_pct", "rendimiento_anterior_t_ha", "superficie_cosechada_ha"):
        sub = serie.dropna(subset=[control])
        if len(sub) >= 3:
            r, p = stats.pearsonr(sub[control], sub["rendimiento_t_ha"])
            controles[control] = {"r": round(float(r), 3), "p": round(float(p), 4), "n": len(sub)}
    print("\nControles no climaticos vs rendimiento:")
    for k, v in controles.items():
        print(f"  {k:<28} r={v['r']:+.2f} (p={v['p']:.3f}, n={v['n']})")

    avisos = [
        f"El objetivo es de la region {args.region}: las dos zonas comparten el mismo valor, "
        "asi que el efecto de zona NO es identificable con este dato.",
        f"Solo hay {len(anios)} campanas con objetivo ({anios[0]}-{anios[-1]}): insuficiente para "
        "ajustar y validar un modelo (H2 queda fuera de alcance con esta fuente).",
        "El rendimiento distrital no existe publicado (ver cabecera de rendimiento_midagri.py).",
    ]
    print("\nAVISOS:")
    for a in avisos:
        print("  -", a)

    with open(SALIDA_JSON, "w", encoding="utf-8") as fh:
        json.dump({"generado": date.today().isoformat(), "region_objetivo": args.region,
                   "campanas_con_objetivo": [int(anios[0]), int(anios[-1])], "n_campanas": len(anios),
                   "zonas": zonas, "correlaciones": resultados, "controles": controles,
                   "avisos": avisos}, fh, ensure_ascii=False, indent=2)
    for ruta in (SALIDA_CSV, SALIDA_JSON):
        print(f"\nGuardado: {os.path.relpath(ruta, RAIZ)}" if ruta == SALIDA_CSV
              else f"Guardado: {os.path.relpath(ruta, RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
