"""
Z3: contrasta H2 — ¿el clima de la zona predice el rendimiento mejor que no usarlo?

Unidad de analisis: REGION x CAMPANA (decision 17-sep-2026). El objetivo distrital no existe
publicado (ver `rendimiento_midagri.py`), y con las 8 campanas de una sola region no se puede
ajustar ni validar. Se sube a region: 6 regiones palteras de costa con punto de clima verificado
sobre cultivo (~77 % de la superficie nacional) x 8 campanas (2016-2023).

Criterios FIJADOS ANTES DE VER RESULTADOS
-----------------------------------------
Modelo PRIMARIO: M2 = Ridge sobre las 5 climaticas clave de Z1 + 2 controles no climaticos.
Los demas modelos son secundarios y se reportan para contexto, no para elegir el mejor a posteriori.

Lineas base:
  B0 media de la region (nivel historico, sin clima)
  B1 persistencia (el rendimiento de la campana anterior de esa region)

Validaciones (ambas exigidas):
  LOYO  dejar una campana fuera  -> generalizar a un ano nuevo
  LORO  dejar una region fuera   -> generalizar a una zona nueva (lo que pide la premisa del asesor)

H2 SE CUMPLE si el modelo primario supera a B0 **y** a B1 (skill = 1 - MAE_modelo/MAE_base > 0)
en las DOS validaciones.

Salidas: datos/zonas/experimento_z3.json (+ experimento_z3.png si hay matplotlib)

Uso (desde sistema_palta/)
--------------------------
    python scripts/zonas/experimento_z3.py
    python scripts/zonas/experimento_z3.py --sin-figura
"""
import sys
import os
import json
import argparse
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")          # consola Windows cp1252 (ver CLAUDE.md)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

import numpy as np                                                       # noqa: E402
import pandas as pd                                                      # noqa: E402
from sklearn.linear_model import Ridge                                   # noqa: E402
from sklearn.ensemble import RandomForestRegressor                       # noqa: E402
from sklearn.pipeline import make_pipeline                               # noqa: E402
from sklearn.preprocessing import StandardScaler                         # noqa: E402
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score  # noqa: E402

CLIMA = os.path.join(RAIZ, "datos", "zonas", "clima_regiones.csv")
RENDIMIENTO = os.path.join(RAIZ, "datos", "zonas", "rendimiento_midagri.csv")
PUNTOS = os.path.join(RAIZ, "datos", "zonas", "puntos_regiones.json")
SALIDA = os.path.join(RAIZ, "datos", "zonas", "experimento_z3.json")
FIGURA = os.path.join(RAIZ, "datos", "zonas", "experimento_z3.png")

CLIMATICAS = ["hfrio_19", "hac_25", "eto", "humedad", "t_min"]     # las 5 clave de Z1
CONTROLES = ["var_superficie_pct", "rend_anterior_t_ha"]           # expansion de huertos y veceria
PRIMARIO = "M2 Ridge clima+controles"


def cargar_panel():
    """Panel region x campana: clima + objetivo + controles, solo regiones con punto verificado."""
    clima = pd.read_csv(CLIMA)
    rend = pd.read_csv(RENDIMIENTO)
    rend = rend[rend["ambito"] == "region"].copy()

    rend = rend.sort_values(["region", "anio"])
    rend["var_superficie_pct"] = rend.groupby("region")["superficie_cosechada_ha"].pct_change() * 100
    rend["rend_anterior_t_ha"] = rend.groupby("region")["rendimiento_t_ha"].shift(1)

    panel = clima.merge(rend[["region", "anio", "rendimiento_t_ha", "superficie_cosechada_ha",
                              "var_superficie_pct", "rend_anterior_t_ha"]],
                        on=["region", "anio"], how="inner")
    return panel.dropna(subset=["rendimiento_t_ha"] + CLIMATICAS).sort_values(["region", "anio"])


def modelos():
    """Modelos a comparar. El primario esta fijado de antemano; el resto es contexto."""
    return {
        "M1 Ridge clima": (make_pipeline(StandardScaler(), Ridge(alpha=1.0)), CLIMATICAS),
        PRIMARIO: (make_pipeline(StandardScaler(), Ridge(alpha=1.0)), CLIMATICAS + CONTROLES),
        "M3 RF clima+controles": (RandomForestRegressor(
            n_estimators=300, max_depth=3, min_samples_leaf=3, max_features=0.5,
            random_state=42), CLIMATICAS + CONTROLES),
    }


def predecir_base(entrena, prueba, tipo):
    """B0: media de la region en el train (o media global si la region no esta). B1: persistencia."""
    global_media = entrena["rendimiento_t_ha"].mean()
    medias = entrena.groupby("region")["rendimiento_t_ha"].mean()
    if tipo == "B0":
        return prueba["region"].map(medias).fillna(global_media).to_numpy()
    anterior = prueba["rend_anterior_t_ha"]
    respaldo = prueba["region"].map(medias).fillna(global_media)
    return anterior.fillna(respaldo).to_numpy()     # la 1a campana de cada region no tiene anterior


def validar(panel, columna_grupo):
    """Predicciones fuera de muestra dejando fuera cada valor de `columna_grupo` (ano o region)."""
    y = panel["rendimiento_t_ha"].to_numpy()
    pred = {nombre: np.full(len(panel), np.nan) for nombre in list(modelos()) + ["B0", "B1"]}
    for grupo in sorted(panel[columna_grupo].unique()):
        fuera = panel[columna_grupo] == grupo
        entrena, prueba = panel[~fuera], panel[fuera]
        if entrena.empty:
            continue
        for base in ("B0", "B1"):
            pred[base][fuera.to_numpy()] = predecir_base(entrena, prueba, base)
        for nombre, (estimador, columnas) in modelos().items():
            xtr = entrena[columnas].fillna(entrena[columnas].median())
            xte = prueba[columnas].fillna(entrena[columnas].median())
            modelo = estimador.fit(xtr, entrena["rendimiento_t_ha"])
            pred[nombre][fuera.to_numpy()] = modelo.predict(xte)
    return y, pred


def metricas(y, p):
    return {"mae": round(float(mean_absolute_error(y, p)), 3),
            "rmse": round(float(np.sqrt(mean_squared_error(y, p))), 3),
            "r2": round(float(r2_score(y, p)), 3)}


def prueba_anomalias(panel):
    """
    EXPLORATORIO (no estaba preinscrito): ¿el clima explica la desviacion de cada campana respecto
    al nivel historico de SU region?

    Los modelos principales tienen que aprender de cero el nivel de cada region a partir del clima,
    que es mucho pedir con 6 regiones. Aqui se les regala ese nivel: se predice solo la anomalia
    (rendimiento - media de la region, ambas del train) con anomalias climaticas. Si ni asi el clima
    aporta, la conclusion de H2 es mas solida.

    Devuelve (mae_modelo, mae_base), donde la base es "anomalia = 0" (es decir, B0).
    """
    y = panel["rendimiento_t_ha"].to_numpy()
    pred = np.full(len(panel), np.nan)
    base = np.full(len(panel), np.nan)
    for anio in sorted(panel["anio"].unique()):
        fuera = (panel["anio"] == anio).to_numpy()
        entrena, prueba = panel[~fuera], panel[fuera]
        nivel = entrena.groupby("region")["rendimiento_t_ha"].mean()
        clima_medio = entrena.groupby("region")[CLIMATICAS].mean()
        global_nivel = entrena["rendimiento_t_ha"].mean()

        def anomalias(df):
            niveles = df["region"].map(nivel).fillna(global_nivel)
            base_clima = clima_medio.reindex(df["region"]).to_numpy()
            return df[CLIMATICAS].to_numpy() - base_clima, niveles.to_numpy()

        xtr, nivel_tr = anomalias(entrena)
        xte, nivel_te = anomalias(prueba)
        modelo = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        modelo.fit(xtr, entrena["rendimiento_t_ha"].to_numpy() - nivel_tr)
        pred[fuera] = nivel_te + modelo.predict(xte)
        base[fuera] = nivel_te
    return (float(mean_absolute_error(y, pred)), float(mean_absolute_error(y, base)))


def main():
    ap = argparse.ArgumentParser(description="Contrasta H2 en el panel region x campana (Z3).")
    ap.add_argument("--sin-figura", action="store_true")
    args = ap.parse_args()

    for ruta, quien in ((CLIMA, "scripts/zonas/clima_regiones.py"),
                        (RENDIMIENTO, "scripts/zonas/rendimiento_midagri.py")):
        if not os.path.exists(ruta):
            print(f"Falta {os.path.relpath(ruta, RAIZ)}. Corre antes: python {quien}")
            return 1

    panel = cargar_panel()
    regiones = sorted(panel["region"].unique())
    anios = sorted(panel["anio"].unique())
    print(f"Panel: {len(panel)} filas · {len(regiones)} regiones ({', '.join(regiones)}) · "
          f"campanas {anios[0]}-{anios[-1]}")
    print(f"Rendimiento: media {panel['rendimiento_t_ha'].mean():.1f} t/ha · "
          f"rango {panel['rendimiento_t_ha'].min():.1f}-{panel['rendimiento_t_ha'].max():.1f} · "
          f"desviacion {panel['rendimiento_t_ha'].std():.1f}")
    if len(panel) < 30:
        print("AVISO: menos de 30 filas; los resultados son indicativos.")

    resultados = {}
    for etiqueta, columna in (("LOYO (deja una campana fuera)", "anio"),
                              ("LORO (deja una region fuera)", "region")):
        y, pred = validar(panel, columna)
        base_mae = {b: mean_absolute_error(y, pred[b]) for b in ("B0", "B1")}
        print(f"\n== {etiqueta} ==")
        print(f"  {'modelo':<26}{'MAE':>7}{'RMSE':>8}{'R2':>7}{'skill B0':>10}{'skill B1':>10}")
        fila_resultados = {}
        for nombre in ["B0", "B1"] + list(modelos()):
            m = metricas(y, pred[nombre])
            skill_b0 = 1 - m["mae"] / base_mae["B0"]
            skill_b1 = 1 - m["mae"] / base_mae["B1"]
            fila_resultados[nombre] = {**m, "skill_b0": round(skill_b0, 3),
                                       "skill_b1": round(skill_b1, 3)}
            marca = " <- primario" if nombre == PRIMARIO else ""
            print(f"  {nombre:<26}{m['mae']:>7.2f}{m['rmse']:>8.2f}{m['r2']:>7.2f}"
                  f"{skill_b0:>+10.2f}{skill_b1:>+10.2f}{marca}")
        resultados[columna] = fila_resultados

    primario = {k: resultados[k][PRIMARIO] for k in resultados}
    cumple = all(v["skill_b0"] > 0 and v["skill_b1"] > 0 for v in primario.values())
    print(f"\nCriterio: el modelo primario ({PRIMARIO}) debe superar a B0 y B1 en LOYO y LORO.")
    for k, v in primario.items():
        print(f"  {k}: skill vs B0 = {v['skill_b0']:+.2f} · vs B1 = {v['skill_b1']:+.2f}")
    print(f"\nVEREDICTO H2: {'SE CUMPLE' if cumple else 'NO SE CUMPLE'}")

    mae_anom, mae_base_anom = prueba_anomalias(panel)
    skill_anom = 1 - mae_anom / mae_base_anom
    print(f"\nEXPLORATORIO (no preinscrito) — clima sobre la anomalia de cada region, LOYO:")
    print(f"  MAE con clima {mae_anom:.2f} vs {mae_base_anom:.2f} sin clima -> skill {skill_anom:+.2f}")
    print("  " + ("el clima aporta algo sobre el nivel de la region" if skill_anom > 0
                  else "ni regalandole el nivel de la region el clima aporta"))

    if not args.sin_figura:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ejes = plt.subplots(1, 2, figsize=(11, 5))
            for eje, (etiqueta, columna) in zip(ejes, (("LOYO", "anio"), ("LORO", "region"))):
                y, pred = validar(panel, columna)
                for nombre, color in ((PRIMARIO, "#2f6fd0"), ("B0", "#999999")):
                    eje.scatter(y, pred[nombre], label=nombre, alpha=0.8,
                                color=color, edgecolor="white", s=55)
                lim = [min(y) - 2, max(y) + 2]
                eje.plot(lim, lim, "k--", lw=1)
                eje.set_xlabel("rendimiento real (t/ha)")
                eje.set_ylabel("predicho (t/ha)")
                eje.set_title(etiqueta)
                eje.legend()
                eje.grid(alpha=0.3)
            fig.suptitle("Z3 · predicción fuera de muestra del rendimiento regional de palta")
            fig.tight_layout()
            fig.savefig(FIGURA, dpi=140)
            print(f"Guardado: {os.path.relpath(FIGURA, RAIZ)}")
        except ImportError:
            print("(sin figura: matplotlib no esta instalado)")

    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump({"generado": date.today().isoformat(),
                   "unidad": "region x campana", "regiones": regiones,
                   "campanas": [int(anios[0]), int(anios[-1])], "filas": len(panel),
                   "features_clima": CLIMATICAS, "controles": CONTROLES,
                   "modelo_primario": PRIMARIO,
                   "criterio": "skill > 0 frente a B0 y B1 en LOYO y LORO",
                   "resultados": resultados, "h2_se_cumple": bool(cumple),
                   "exploratorio_anomalias": {"mae_con_clima": round(mae_anom, 3),
                                              "mae_sin_clima": round(mae_base_anom, 3),
                                              "skill": round(skill_anom, 3),
                                              "nota": "no preinscrito; LOYO sobre anomalias por region"}},
                  fh, ensure_ascii=False, indent=2)
    print(f"Guardado: {os.path.relpath(SALIDA, RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
