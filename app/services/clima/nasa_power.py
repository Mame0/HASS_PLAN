"""
Proveedor NASA POWER (hourly point) — FALLBACK.

Gratis, sin API key, cobertura global. Entrega T2M, RH2M y PRECTOTCORR horarios.
No entrega ETO de forma directa en el endpoint horario, por lo que `eto` queda vacío
(el motor lo reportará como None y el modelo lo tratará como faltante).
Doc: https://power.larc.nasa.gov/docs/services/api/temporal/hourly/
"""
import requests

from app.services.clima.base import ProveedorClima, SerieHoraria

ENDPOINT = "https://power.larc.nasa.gov/api/temporal/hourly/point"
TIMEOUT = 40


class NasaPower(ProveedorClima):
    tipo = "nasa_power"

    def obtener_serie(self, lat, lon, desde, hasta) -> SerieHoraria:
        params = {
            "parameters": "T2M,RH2M,PRECTOTCORR",
            "community": "AG",
            "longitude": lon,
            "latitude": lat,
            "start": desde.strftime("%Y%m%d"),
            "end": hasta.strftime("%Y%m%d"),
            "format": "JSON",
        }
        r = requests.get(ENDPOINT, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        param = r.json()["properties"]["parameter"]

        # Cada parámetro es un dict {YYYYMMDDHH: valor}; se ordena por la clave temporal.
        def serie(nombre):
            d = param.get(nombre, {})
            return [d[k] for k in sorted(d.keys())]

        return SerieHoraria(
            temperatura=serie("T2M"),
            humedad=serie("RH2M"),
            precipitacion=serie("PRECTOTCORR"),
            eto=[],  # no disponible en el endpoint horario
        )
