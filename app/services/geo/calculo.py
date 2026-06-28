"""
Calculo de centroide y area desde GeoJSON (Polygon o Point), en Python puro.

GeoJSON usa orden [lon, lat]. Acepta Geometry, Feature o FeatureCollection.
- centroide(): centroide del poligono (formula del area firmada) o el propio punto.
- area_ha(): area en hectareas via proyeccion local equirectangular (0 para Point).
"""
import json
from math import cos, radians

M_POR_GRADO_LAT = 110574.0   # metros por grado de latitud (promedio)
M_POR_GRADO_LON = 111320.0   # metros por grado de longitud en el ecuador (se escala por cos(lat))


def _geometria(gj):
    """Normaliza str/dict y extrae el dict de geometry (Polygon/Point)."""
    if isinstance(gj, str):
        gj = json.loads(gj)
    if gj.get("type") == "FeatureCollection":
        if not gj.get("features"):
            raise ValueError("FeatureCollection vacio.")
        gj = gj["features"][0]
    if gj.get("type") == "Feature":
        gj = gj["geometry"]
    if not gj or "type" not in gj:
        raise ValueError("GeoJSON sin geometria valida.")
    return gj


def _anillo(geom):
    """Anillo exterior de un Polygon como lista de [lon, lat] (sin repetir el cierre)."""
    ring = geom["coordinates"][0]
    return ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring


def centroide(gj):
    """Devuelve (lat, lon) del centroide. Para Point, el propio punto."""
    geom = _geometria(gj)
    t = geom["type"]
    if t == "Point":
        lon, lat = geom["coordinates"][:2]
        return lat, lon
    if t == "Polygon":
        pts = _anillo(geom)
        n = len(pts)
        if n < 3:
            lon = sum(p[0] for p in pts) / n
            lat = sum(p[1] for p in pts) / n
            return lat, lon
        a = cx = cy = 0.0
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            cross = x0 * y1 - x1 * y0
            a += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
        if a == 0:  # degenerado: promedio simple
            lon = sum(p[0] for p in pts) / n
            lat = sum(p[1] for p in pts) / n
            return lat, lon
        cx /= (3 * a)
        cy /= (3 * a)
        return cy, cx  # (lat, lon)
    raise ValueError(f"Geometria no soportada: {t}")


def area_ha(gj):
    """Area en hectareas (0.0 para Point). Proyeccion local equirectangular."""
    geom = _geometria(gj)
    if geom["type"] != "Polygon":
        return 0.0
    pts = _anillo(geom)
    n = len(pts)
    if n < 3:
        return 0.0
    lat0 = sum(p[1] for p in pts) / n
    k = cos(radians(lat0))
    a = 0.0
    for i in range(n):
        x0 = pts[i][0] * k * M_POR_GRADO_LON
        y0 = pts[i][1] * M_POR_GRADO_LAT
        x1 = pts[(i + 1) % n][0] * k * M_POR_GRADO_LON
        y1 = pts[(i + 1) % n][1] * M_POR_GRADO_LAT
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0 / 10000.0


def resumen(gj):
    """{tipo, centro_lat, centro_lon, area_ha} listo para volcar en el Lote."""
    geom = _geometria(gj)
    lat, lon = centroide(geom)
    return {
        "tipo": geom["type"],
        "centro_lat": round(lat, 6),
        "centro_lon": round(lon, 6),
        "area_ha": round(area_ha(geom), 4),
    }
