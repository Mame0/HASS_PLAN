"""Pruebas de geocercas de zona y su muestreo climatico por cuadrantes ERA5-Land (Track Z, sin BD)."""
import math

import pytest

from app.services.geo import (
    area_ha, centroide, cuadrante_de, nodo, id_cuadrante, poligono_cuadrante, partes_geocerca,
    area_geocerca_ha, punto_en_geocerca, anillo_simple, se_solapan, muestreo_clima,
)

LAT0, LON0 = -16.59, -71.92          # lotes de La Joya; celda -16.6_-71.9
M_LAT = 1 / 110574


def m_lon(lat=LAT0):
    return 1 / (111320 * math.cos(math.radians(lat)))


def rect(lat, lon, alto_m, ancho_m):
    """Rectangulo con esquina inferior izquierda en (lat, lon), medidas en metros."""
    dlat, dlon = alto_m * M_LAT, ancho_m * m_lon(lat)
    return {"type": "Polygon", "coordinates": [[
        [lon, lat], [lon + dlon, lat], [lon + dlon, lat + dlat], [lon, lat + dlat], [lon, lat],
    ]]}


def rect_grados(s, w, n, e):
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def multi(*poligonos):
    return {"type": "MultiPolygon", "coordinates": [p["coordinates"] for p in poligonos]}


# --- rejilla de clima -----------------------------------------------------------------

def test_cuadrante_es_el_nodo_mas_cercano():
    assert nodo(*cuadrante_de(-16.59, -71.92)) == (-16.6, -71.9)
    assert nodo(*cuadrante_de(-16.64, -71.96)) == (-16.6, -72.0)
    assert nodo(*cuadrante_de(-16.36, -72.19)) == (-16.4, -72.2)


def test_borde_de_celda_va_al_norte_y_al_este():
    assert nodo(*cuadrante_de(-16.55, -71.95)) == (-16.5, -71.9)


def test_id_legible_y_estable():
    assert id_cuadrante(*cuadrante_de(-16.59, -71.92)) == "-16.6_-71.9"
    assert id_cuadrante(-160, -720) == "-16.0_-72.0"


def test_poligono_cuadrante_centrado_en_el_nodo_y_de_0_1_grados():
    celda = poligono_cuadrante(*cuadrante_de(-16.59, -71.92))
    lat, lon = centroide(celda)
    assert abs(lat + 16.6) < 1e-6
    assert abs(lon + 71.9) < 1e-6
    esperado = (0.1 * 110574) * (0.1 * 111320 * math.cos(math.radians(-16.6))) / 10000
    assert abs(area_ha(celda) - esperado) / esperado < 0.01          # ~11 900 ha


def test_todo_punto_de_la_celda_vuelve_a_su_cuadrante():
    i, j = cuadrante_de(-16.59, -71.92)
    nlat, nlon = nodo(i, j)
    for lon, lat in poligono_cuadrante(i, j)["coordinates"][0][:4]:
        adentro = (lat + (nlat - lat) * 0.001, lon + (nlon - lon) * 0.001)   # esquina, un pelo hacia el nodo
        assert cuadrante_de(*adentro) == (i, j)


# --- geocercas ----------------------------------------------------------------------------

SUR = rect(LAT0, LON0, 1000, 1000)                       # 100 ha
NORTE = rect(LAT0 + 20000 * M_LAT, LON0, 1000, 1000)     # otra parte, 20 km al norte
DOS_PARTES = multi(SUR, NORTE)


def test_area_geocerca_suma_las_partes():
    assert abs(area_geocerca_ha(DOS_PARTES) - 200.0) < 2.0


def test_punto_en_segunda_parte_y_no_en_el_desierto_intermedio():
    assert punto_en_geocerca(LAT0 + 20500 * M_LAT, LON0 + 500 * m_lon(), DOS_PARTES)
    assert not punto_en_geocerca(LAT0 + 10000 * M_LAT, LON0 + 500 * m_lon(), DOS_PARTES)


def test_contorno_cruzado_y_geometria_no_soportada():
    assert anillo_simple(partes_geocerca(SUR)[0])
    assert not anillo_simple([[0, 0], [1, 1], [1, 0], [0, 1]])      # dibujado "en ocho"
    with pytest.raises(ValueError):
        partes_geocerca({"type": "Point", "coordinates": [LON0, LAT0]})


def test_se_solapan():
    lejos = rect(LAT0, LON0 + 5000 * m_lon(), 1000, 1000)
    cruzada = rect(LAT0 + 500 * M_LAT, LON0 + 500 * m_lon(), 1000, 1000)
    adentro = rect(LAT0 + 400 * M_LAT, LON0 + 400 * m_lon(), 100, 100)
    assert not se_solapan(SUR, lejos)
    assert se_solapan(SUR, cruzada)
    assert se_solapan(SUR, adentro)
    assert se_solapan(adentro, DOS_PARTES)


# --- muestreo climatico -----------------------------------------------------------------

def test_muestreo_geocerca_dentro_de_una_celda():
    zona = rect(LAT0, LON0, 2000, 2000)                  # 400 ha
    (c,) = muestreo_clima(zona)
    assert c["id"] == "-16.6_-71.9"
    assert abs(c["area_ha"] - area_ha(zona)) < 0.5
    lat, lon = centroide(zona)
    assert abs(c["punto_lat"] - lat) < 1e-5
    assert abs(c["punto_lon"] - lon) < 1e-5
    assert c["punto_metodo"] == "centroide"


def test_muestreo_reparte_entre_celdas_vecinas():
    zona = rect_grados(-16.60, -71.87, -16.58, -71.83)   # cruza el borde lon -71.85
    oeste, este = muestreo_clima(zona)
    assert (oeste["id"], este["id"]) == ("-16.6_-71.9", "-16.6_-71.8")
    assert abs(oeste["area_ha"] + este["area_ha"] - area_ha(zona)) < 1.0
    assert oeste["punto_lon"] < -71.85 < este["punto_lon"]


def test_muestreo_descarta_bordes_rozados():
    zona = rect_grados(-16.60, -71.90, -16.58, -71.849)  # ~24 ha asoman a la celda este
    assert [c["id"] for c in muestreo_clima(zona)] == ["-16.6_-71.9"]


def test_muestreo_geocerca_chica_conserva_su_celda():
    (c,) = muestreo_clima(rect(LAT0, LON0, 100, 100))
    assert c["id"] == "-16.6_-71.9"
    assert abs(c["area_ha"] - 1.0) < 0.05


def test_muestreo_geocerca_en_u_usa_punto_interior():
    # U de 1 km con muesca central de 400 m x 800 m: el centroide cae dentro de la muesca.
    xy = [(0, 0), (1000, 0), (1000, 1000), (700, 1000), (700, 200), (300, 200), (300, 1000), (0, 1000)]
    anillo = [[LON0 + x * m_lon(), LAT0 + y * M_LAT] for x, y in xy]
    zona = {"type": "Polygon", "coordinates": [anillo + [anillo[0]]]}
    assert not punto_en_geocerca(*centroide(zona), zona)
    (c,) = muestreo_clima(zona)
    assert c["punto_metodo"] == "interior"
    assert punto_en_geocerca(c["punto_lat"], c["punto_lon"], zona)


def test_muestreo_partes_separadas_en_la_misma_celda():
    a = rect(LAT0, LON0, 1000, 1000)
    b = rect(LAT0, LON0 + 3000 * m_lon(), 1000, 1000)    # el promedio de ambas cae en el hueco
    (c,) = muestreo_clima(multi(a, b))
    assert abs(c["area_ha"] - 200.0) < 2.0
    assert c["punto_metodo"] == "interior"
    assert punto_en_geocerca(c["punto_lat"], c["punto_lon"], multi(a, b))


def test_muestreo_prefiere_referencia_verificada_en_la_celda():
    zona = rect(LAT0, LON0, 2000, 2000)
    ref = (LAT0 + 300 * M_LAT, LON0 + 1700 * m_lon())
    (c,) = muestreo_clima(zona, referencias=[ref])
    assert c["punto_metodo"] == "referencia"
    assert (c["punto_lat"], c["punto_lon"]) == (round(ref[0], 6), round(ref[1], 6))


def test_muestreo_elige_la_referencia_mas_cercana_al_centro_cubierto():
    zona = rect(LAT0, LON0, 2000, 2000)
    lejos = (LAT0 + 100 * M_LAT, LON0 + 100 * m_lon())
    cerca = (LAT0 + 900 * M_LAT, LON0 + 1100 * m_lon())
    (c,) = muestreo_clima(zona, referencias=[lejos, cerca])
    assert (c["punto_lat"], c["punto_lon"]) == (round(cerca[0], 6), round(cerca[1], 6))


def test_muestreo_ignora_referencias_fuera_de_la_geocerca():
    zona = rect(LAT0, LON0, 2000, 2000)
    fuera = (LAT0 - 500 * M_LAT, LON0 + 500 * m_lon())      # misma celda, fuera del poligono
    (c,) = muestreo_clima(zona, referencias=[fuera])
    assert c["punto_metodo"] == "centroide"
