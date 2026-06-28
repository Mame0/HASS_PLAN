"""
Afina la ubicacion del Fundo Los Paltos (Nepena, Ancash) probando varios puntos
del valle vs la fila del dataset 19-20 (cluster F01). Busca el punto que minimiza
el sesgo calido. Permite pasar elevation para la correccion de downscaling de Open-Meteo.
"""
from datetime import date
import requests

DESDE, HASTA = date(2019, 7, 1), date(2020, 6, 30)
ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"

# Fila dataset F01 19-20
DS = {"t_prom": 19.26, "t_min": 16.83, "t_max": 23.38, "humedad": 85.1,
      "hfrio_19": 3459, "hfrio_14_19": 5066.5, "hac_20_25": 2212.5, "hac_25": 689,
      "eto": 944.72}

# Puntos candidatos: (etiqueta, lat, lon, elevation o None)
PUNTOS = [
    ("approx        ", -9.18, -78.30, None),
    ("pueblo Nepena ", -9.176, -78.337, None),
    ("costa (oeste) ", -9.16, -78.43, None),
    ("adentro (este)", -9.21, -78.25, None),
    ("adentro +alt  ", -9.21, -78.25, 600),
]


def limpiar(v):
    return [x for x in v if x is not None and x > -900]


def prom_diario(v, agg):
    dias = []
    for i in range(0, len(v), 24):
        d = limpiar(v[i:i+24])
        if d:
            dias.append(agg(d))
    return sum(dias)/len(dias) if dias else None


def features(lat, lon, elev):
    p = {"latitude": lat, "longitude": lon, "start_date": DESDE.isoformat(),
         "end_date": HASTA.isoformat(),
         "hourly": "temperature_2m,relative_humidity_2m,precipitation,et0_fao_evapotranspiration",
         "timezone": "auto"}
    if elev is not None:
        p["elevation"] = elev
    h = requests.get(ENDPOINT, params=p, timeout=30).json().get("hourly", {})
    T = limpiar(h.get("temperature_2m", []))
    RH = limpiar(h.get("relative_humidity_2m", []))
    E = limpiar(h.get("et0_fao_evapotranspiration", []))
    return {
        "t_prom": sum(T)/len(T), "t_min": prom_diario(h["temperature_2m"], min),
        "t_max": prom_diario(h["temperature_2m"], max),
        "humedad": sum(RH)/len(RH) if RH else 0,
        "hfrio_19": sum(1 for t in T if t < 19),
        "hfrio_14_19": sum(1 for t in T if 14 <= t < 19),
        "hac_20_25": sum(1 for t in T if 20 <= t < 25),
        "hac_25": sum(1 for t in T if t > 25),
        "eto": sum(E),
    }


print(f"{'Punto':<16}{'Tprom':>7}{'Tmax':>7}{'Hum':>6}{'Frio19':>8}{'Ac>25':>7}{'ETO':>8}  altitud")
print(f"{'DATASET':<16}{DS['t_prom']:>7.1f}{DS['t_max']:>7.1f}{DS['humedad']:>6.0f}"
      f"{DS['hfrio_19']:>8.0f}{DS['hac_25']:>7.0f}{DS['eto']:>8.0f}")
print("-" * 66)
for nombre, lat, lon, elev in PUNTOS:
    try:
        f = features(lat, lon, elev)
        print(f"{nombre:<16}{f['t_prom']:>7.1f}{f['t_max']:>7.1f}{f['humedad']:>6.0f}"
              f"{f['hfrio_19']:>8.0f}{f['hac_25']:>7.0f}{f['eto']:>8.0f}  {elev or 'grid'}")
    except Exception as e:
        print(f"{nombre:<16} ERROR: {e}")
