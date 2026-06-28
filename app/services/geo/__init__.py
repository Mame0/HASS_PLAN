"""
Servicio geo: deriva centroide y area (ha) desde la geometria GeoJSON de un lote.

Sin dependencias externas (no shapely/pyproj). Para parcelas pequenas (pocas ha)
una proyeccion local equirectangular alrededor del centroide da area con error
despreciable. El centroide alimenta la API de clima; el area reemplaza el campo manual.
"""
from app.services.geo.calculo import centroide, area_ha, resumen

__all__ = ["centroide", "area_ha", "resumen"]
