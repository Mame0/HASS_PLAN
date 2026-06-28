"""
Cuantifica la BRECHA DE DOMINIO entre el sitio de entrenamiento (Nepena, costa)
y el de despliegue (La Joya, desierto). Misma ventana 19-20, las 12 climaticas.
Si los climas son muy distintos, el modelo extrapola al predecir en La Joya.
"""
from datetime import date
import requests

DESDE, HASTA = date(2019, 7, 1), date(2020, 6, 30)
ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"

SITIOS = {
    "NEPENA (train)": (-9.16, -78.43),   # Fundo Los Paltos, costa Ancash
    "LA JOYA (deploy)": (-16.59, -71.92),  # desierto Arequipa, ~1300 m
}


def limpiar(v):
    return [x for x in v if x is not None and x > -900]


def prom_diario(v, agg):
    dias = []
    for i in range(0, len(v), 24):
        d = limpiar(v[i:i+24])
        if d:
            dias.append(agg(d))
    return sum(dias)/len(dias) if dias else 0


def features(lat, lon):
    p = {"latitude": lat, "longitude": lon, "start_date": DESDE.isoformat(),
         "end_date": HASTA.isoformat(),
         "hourly": "temperature_2m,relative_humidity_2m,precipitation,et0_fao_evapotranspiration",
         "timezone": "auto"}
    h = requests.get(ENDPOINT, params=p, timeout=30).json().get("hourly", {})
    T = limpiar(h.get("temperature_2m", []))
    RH = limpiar(h.get("relative_humidity_2m", []))
    P = limpiar(h.get("precipitation", []))
    E = limpiar(h.get("et0_fao_evapotranspiration", []))
    return {
        "H.Frio<19": sum(1 for t in T if t < 19),
        "H.Frio<15": sum(1 for t in T if t < 15),
        "H.Frio14-19": sum(1 for t in T if 14 <= t < 19),
        "H.Ac20-25": sum(1 for t in T if 20 <= t < 25),
        "H.Ac>25": sum(1 for t in T if t > 25),
        "T_Prom": sum(T)/len(T),
        "T_Min": prom_diario(h["temperature_2m"], min),
        "T_Max": prom_diario(h["temperature_2m"], max),
        "Humedad%": sum(RH)/len(RH) if RH else 0,
        "Lluvia": sum(P),
        "ETO": sum(E),
    }


datos = {nombre: features(lat, lon) for nombre, (lat, lon) in SITIOS.items()}
claves = list(next(iter(datos.values())).keys())

print(f"{'Variable':<13}{'NEPENA':>10}{'LA JOYA':>10}{'brecha':>9}")
print("-" * 42)
for k in claves:
    a = datos["NEPENA (train)"][k]
    b = datos["LA JOYA (deploy)"][k]
    dif = (b - a) / a * 100 if a else float('nan')
    print(f"{k:<13}{a:>10.1f}{b:>10.1f}{dif:>8.0f}%")
