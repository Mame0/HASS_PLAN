"""
Reentrena el Random Forest sobre el PIPELINE DE LA API (Fase 1 ROADMAP + B4).

Diferencia con el notebook original: las 12 climaticas NO salen del CSV, se DERIVAN
con Open-Meteo en Nepena (Fundo Los Paltos) usando la MISMA funcion de produccion
(app.services.clima.derivar), una serie regional por campana. Las 5 manuales (en
realidad 3: riego, edad_campo, edad_prod) y el target salen del CSV.

Asi train (Nepena) e inferencia (La Joya) comparten tuberia: el offset de ETO y el
artefacto de lluvia dejan de importar porque el modelo aprende en unidades de la API.

Salida: app/ml/modelo.pkl + app/ml/modelo_meta.json (orden de features, rangos para
bandera OOD, metricas, coords, ventanas).
"""
import sys, os, json
from datetime import date
from statistics import mean

import numpy as np
import pandas as pd
import requests
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, GroupKFold, cross_val_score, GridSearchCV
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error

# --- usar la funcion de derivacion de PRODUCCION para garantizar consistencia ---
SISTEMA = r"c:\Tesis\sistema_palta"
sys.path.insert(0, SISTEMA)
from app.services.clima.base import SerieHoraria
from app.services.clima.derivar import derivar_features

CSV = r"c:\Tesis\MODELO\Modelo_ml\sample_data\Dataset_Limpio_ML.csv"
OUT_PKL = os.path.join(SISTEMA, "app", "ml", "modelo.pkl")
OUT_META = os.path.join(SISTEMA, "app", "ml", "modelo_meta.json")

LAT, LON = -9.16, -78.43          # Fundo Los Paltos, costa Nepena (punto validado)
ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"

# Orden EXACTO que espera el backend (RegistroAgronomico.FEATURES)
FEATURES = ["edad_campo", "edad_prod", "riego_m3ha",
            "hfrio_19", "hfrio_14_19", "hfrio_14", "hfrio_15",
            "hac_20_25", "hac_25",
            "humedad", "eto", "t_min", "t_max", "t_prom", "lluvia"]


def ventana(campana: str):
    """'19 - 20' -> (2019-07-01, 2020-06-30). Campana de mitad a mitad de ano."""
    ini = int(campana.split("-")[0].strip())
    y0 = 2000 + ini
    return date(y0, 7, 1), date(y0 + 1, 6, 30)


def clima_api(desde, hasta):
    """Serie horaria Open-Meteo -> 12 features via derivar_features (produccion)."""
    p = {"latitude": LAT, "longitude": LON, "start_date": desde.isoformat(),
         "end_date": hasta.isoformat(),
         "hourly": "temperature_2m,relative_humidity_2m,precipitation,et0_fao_evapotranspiration",
         "timezone": "auto"}
    h = requests.get(ENDPOINT, params=p, timeout=60).json().get("hourly", {})
    serie = SerieHoraria(
        temperatura=h.get("temperature_2m", []),
        humedad=h.get("relative_humidity_2m", []),
        precipitacion=h.get("precipitation", []),
        eto=h.get("et0_fao_evapotranspiration", []),
    )
    return derivar_features(serie)


def num(s):
    return float(str(s).replace(",", ".")) if str(s).strip() not in ("", "N/D", "nan") else np.nan


# ----------------------------------------------------------------------------
df = pd.read_csv(CSV, encoding="latin-1", sep=";")
cols = {c: c for c in df.columns}
col_camp = next(c for c in df.columns if "Campa" in c)
col_y = next(c for c in df.columns if "Tn/Ha" in c)
col_riego = next(c for c in df.columns if "Riego" in c)
col_ecampo = next(c for c in df.columns if "Edad" in c and "Campo" in c)
col_eprod = next(c for c in df.columns if "Edad" in c and "Prod" in c)

# Clima derivado por campana (una sola llamada API por campana, cacheado)
campanas = sorted(df[col_camp].str.strip().unique(),
                  key=lambda c: int(c.split("-")[0].strip()))
print("Derivando clima por campana en Nepena...")
clima_cache = {}
for c in campanas:
    d, h = ventana(c)
    clima_cache[c] = clima_api(d, h)
    print(f"  {c}: {d}->{h}  hfrio19={clima_cache[c]['hfrio_19']:.0f} eto={clima_cache[c]['eto']:.0f}")

# Construir X (orden FEATURES) e y
filas, y = [], []
for _, r in df.iterrows():
    camp = str(r[col_camp]).strip()
    cl = clima_cache[camp]
    fila = {
        "edad_campo": max(0, int(r[col_ecampo])),   # clip edades negativas (F46)
        "edad_prod": max(0, int(r[col_eprod])),
        "riego_m3ha": num(r[col_riego]),
        **{k: cl[k] for k in ["hfrio_19", "hfrio_14_19", "hfrio_14", "hfrio_15",
                              "hac_20_25", "hac_25", "humedad", "eto",
                              "t_min", "t_max", "t_prom", "lluvia"]},
    }
    filas.append([fila[f] for f in FEATURES])
    y.append(float(r[col_y]))

X = pd.DataFrame(filas, columns=FEATURES)
y = np.array(y)
# quitar filas con riego faltante
mask = ~X["riego_m3ha"].isna()
X, y, grupos = X[mask], y[mask], df.loc[mask.values, col_camp].str.strip().values
print(f"\nDataset: {X.shape[0]} filas x {X.shape[1]} features")

def confianza_media(forest, Xdf):
    """Confianza promedio (= 100 - CV entre arboles) que veria la API sobre estas filas.
    Misma formula que app/ml/predictor.py, para comparar baseline vs tuneado."""
    Xv = Xdf.to_numpy()
    por_arbol = np.array([t.predict(Xv) for t in forest.estimators_])  # (n_arboles, n_filas)
    media = por_arbol.mean(axis=0)
    cv = np.where(media != 0, por_arbol.std(axis=0) / np.abs(media), 0.0)
    return float(np.clip(100 * (1 - cv), 0, 100).mean())


def evaluar(estimador, etiqueta):
    """R2/MAE/RMSE en split aleatorio + R2 GroupKFold honesto + confianza media."""
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    m = estimador.fit(Xtr, ytr)
    pr = m.predict(Xte)
    r2 = r2_score(yte, pr); mae = mean_absolute_error(yte, pr)
    rmse = float(np.sqrt(mean_squared_error(yte, pr)))
    gkf = GroupKFold(n_splits=min(5, len(set(grupos))))
    cv = cross_val_score(estimador, X, y, groups=grupos, cv=gkf, scoring="r2")
    conf = confianza_media(estimador.fit(X, y), X)
    print(f"[{etiqueta:<16}] R2_split={r2:.2f}  MAE={mae:.2f}  RMSE={rmse:.2f}  "
          f"R2_GKF={cv.mean():+.2f}(+/-{cv.std():.2f})  confianza~{conf:.0f}%")
    return {"r2_split": round(r2, 3), "mae": round(mae, 2), "rmse": round(rmse, 2),
            "r2_groupkfold": round(float(cv.mean()), 3), "confianza_media": round(conf, 1)}


print("\n--- Comparacion baseline vs tuneado (mismas 15 features) ---")
m_base = evaluar(RandomForestRegressor(n_estimators=100, random_state=42), "baseline")

# --- Tuneo: regularizar SIN quitar features. max_features<1 obliga a los arboles
# a cortar por edad/riego y no dejar que las climaticas colineales acaparen cada corte.
# Se optimiza contra GroupKFold (generalizacion honesta a campanas nuevas), no el split. ---
gkf = GroupKFold(n_splits=min(5, len(set(grupos))))
grid = GridSearchCV(
    RandomForestRegressor(n_estimators=300, random_state=42),
    param_grid={
        "max_depth": [4, 6, 8, None],
        "min_samples_leaf": [1, 3, 5],
        "max_features": ["sqrt", 0.5, 1.0],
    },
    cv=gkf, scoring="r2", n_jobs=-1,
)
grid.fit(X, y, groups=grupos)
best = grid.best_params_
print(f"\nMejores hiperparametros (GroupKFold): {best}")
m_tuned = evaluar(RandomForestRegressor(n_estimators=300, random_state=42, **best), "tuneado")

# Importancias del modelo tuneado
modelo_final = RandomForestRegressor(n_estimators=300, random_state=42, **best).fit(X, y)
imp = pd.Series(modelo_final.feature_importances_, index=FEATURES).sort_values(ascending=False)
print("\nImportancias (tuneado):")
for k, v in imp.items():
    print(f"  {k:<12}{v:.3f}")

# --- Modelo final sobre TODO el dataset + metadata ---
os.makedirs(os.path.dirname(OUT_PKL), exist_ok=True)
joblib.dump(modelo_final, OUT_PKL)

meta = {
    "features": FEATURES,
    "rangos_entrenamiento": {f: [float(X[f].min()), float(X[f].max())] for f in FEATURES},
    "metricas": m_tuned,
    "metricas_baseline": m_base,
    "hiperparametros": {"n_estimators": 300, **best},
    "pipeline": {"fuente_clima": "open_meteo", "sitio_entrenamiento": "Nepena (Fundo Los Paltos)",
                 "lat": LAT, "lon": LON, "ventana": "jul-jun por campana",
                 "n_filas": int(X.shape[0])},
    "nota": "Clima derivado por API (no columnas originales). Modelo regularizado (max_features<1 + "
            "min_samples_leaf) para evitar que las climaticas colineales dominen, SIN quitarlas. "
            "Tuneado contra GroupKFold. Usar rangos_entrenamiento para marcar OOD (ej. La Joya).",
}
with open(OUT_META, "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

print(f"\nGuardado: {OUT_PKL}")
print(f"Guardado: {OUT_META}")
