"""
Validación del motor climático en la ubicación REAL del dataset: Fundo Los Paltos, Nepeña (Áncash).
Campaña 19-20 completa (mid-2019 a mid-2020) vs la fila del dataset (cluster F01).
"""
from datetime import date
import sys, os

# raiz del proyecto (sistema_palta/) = dos niveles arriba de scripts/analisis/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.services.clima.open_meteo import OpenMeteo
from app.services.clima.derivar import derivar_features

# Nepeña, Áncash (RJHP+97X ~ -9.18, -78.30)
LAT, LON = -9.18, -78.30
DESDE, HASTA = date(2019, 7, 1), date(2020, 6, 30)  # campaña 19-20, mitad a mitad de año

# Fila del dataset: F01, campaña 19-20 (cluster A)
DATASET = {
    "hfrio_19": 3459, "hfrio_15": 1176, "hfrio_14": 202, "hfrio_14_19": 5066.5,
    "hac_20_25": 2212.5, "hac_25": 689,
    "t_prom": 19.26, "t_min": 16.83, "t_max": 23.38,
    "humedad": 85.1, "lluvia": 9.8, "eto": 944.72,
}

ETIQUETAS = {
    "hfrio_19": "H.Frío<19", "hfrio_15": "H.Frío<15", "hfrio_14": "H.Frío<14",
    "hfrio_14_19": "H.Frío14-19", "hac_20_25": "H.Ac20-25", "hac_25": "H.Ac>25",
    "t_prom": "T_Prom", "t_min": "T_Min", "t_max": "T_Max",
    "humedad": "Humedad%", "lluvia": "Lluvia", "eto": "ETO",
}

print(f"Open-Meteo @ Nepena ({LAT},{LON})  {DESDE} -> {HASTA}")
serie = OpenMeteo().obtener_serie(LAT, LON, DESDE, HASTA)
print(f"Horas recibidas: {serie.horas()}\n")

api = derivar_features(serie)

print(f"{'Variable':<14}{'API':>10}{'Dataset':>10}{'Dif%':>9}")
print("-" * 43)
for k in DATASET:
    a, d = api[k], DATASET[k]
    dp = (a - d) / d * 100 if d else float('nan')
    print(f"{ETIQUETAS[k]:<14}{a:>10.2f}{d:>10.2f}{dp:>8.0f}%")
