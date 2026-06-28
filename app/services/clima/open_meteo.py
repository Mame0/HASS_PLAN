"""
Proveedor Open-Meteo (Archive API) — PRIMARIO.

Gratis, sin API key, resolución horaria. Entrega directamente temperatura, humedad,
precipitación y ETO (Penman-Monteith FAO), que es justo lo que necesita el modelo.
Doc: https://open-meteo.com/en/docs/historical-weather-api
"""
import requests

from app.services.clima.base import ProveedorClima, SerieHoraria

ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
TIMEOUT = 30


class OpenMeteo(ProveedorClima):
    tipo = "open_meteo"

    def obtener_serie(self, lat, lon, desde, hasta) -> SerieHoraria:
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": desde.isoformat(),
            "end_date": hasta.isoformat(),
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,et0_fao_evapotranspiration",
            "timezone": "auto",
        }
        r = requests.get(ENDPOINT, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        h = r.json().get("hourly", {})
        return SerieHoraria(
            temperatura=h.get("temperature_2m", []),
            humedad=h.get("relative_humidity_2m", []),
            precipitacion=h.get("precipitation", []),
            eto=h.get("et0_fao_evapotranspiration", []),
        )
