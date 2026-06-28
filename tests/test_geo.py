"""Pruebas del servicio geo: centroide y area desde GeoJSON (sin BD)."""
import math

from app.services.geo import resumen, centroide, area_ha

# Cuadrado de 100 m x 100 m (= 1 ha) en La Joya, para validar la proyeccion local.
LAT0, LON0 = -16.59, -71.92
DLAT = 100 / 110574
DLON = 100 / (111320 * math.cos(math.radians(LAT0)))
CUADRADO = {"type": "Polygon", "coordinates": [[
    [LON0, LAT0], [LON0 + DLON, LAT0],
    [LON0 + DLON, LAT0 + DLAT], [LON0, LAT0 + DLAT], [LON0, LAT0],
]]}


def test_poligono_area_1ha():
    assert abs(area_ha(CUADRADO) - 1.0) < 0.02


def test_poligono_centroide_centrado():
    lat, lon = centroide(CUADRADO)
    assert abs(lat - (LAT0 + DLAT / 2)) < 1e-4
    assert abs(lon - (LON0 + DLON / 2)) < 1e-4


def test_punto_area_cero_y_centroide_propio():
    r = resumen({"type": "Point", "coordinates": [LON0, LAT0]})
    assert r["area_ha"] == 0.0
    assert abs(r["centro_lat"] - LAT0) < 1e-9
    assert abs(r["centro_lon"] - LON0) < 1e-9


def test_feature_y_featurecollection():
    feat = {"type": "Feature", "properties": {}, "geometry": CUADRADO}
    fc = {"type": "FeatureCollection", "features": [feat]}
    assert abs(area_ha(feat) - 1.0) < 0.02
    assert abs(area_ha(fc) - 1.0) < 0.02


def test_acepta_string_json():
    import json
    assert abs(area_ha(json.dumps(CUADRADO)) - 1.0) < 0.02
