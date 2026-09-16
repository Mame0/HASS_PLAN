"""
Geocercas de zona agroclimatica y su muestreo climatico (Track Z, experimental).

Una ZONA (La Joya, Majes) corresponde a una serie de rendimiento distrital de MIDAGRI. Su
GEOCERCA la delimita el usuario a mano sobre el satelite (criterio del asesor) y puede tener
varias partes separadas por desierto (Polygon o MultiPolygon).

El clima no se resuelve mas fino que la rejilla del reanalisis: ERA5-Land entrega una serie por
nodo de 0.1 grados y todo punto de la celda recibe la de su nodo mas cercano. Por eso la
geocerca se muestrea por CUADRANTES: cada celda que la geocerca cubre aporta una serie, pedida
en un punto de la parte cubierta. Ese punto importa porque Open-Meteo corrige la temperatura
por la altitud del punto pedido: dentro de la geocerca cae sobre cultivo, mientras que el centro
de la celda puede caer en cerro o pampa.

Python puro, como `calculo.py`. GeoJSON usa [lon, lat]; los puntos sueltos, (lat, lon).
"""
from math import floor

from app.services.geo.calculo import _geometria, _anillo, centroide, area_ha

PASO_GRADOS = 0.1        # resolucion de ERA5-Land (models=era5_land en Open-Meteo)
MIN_HA_CUADRANTE = 100   # celdas cubiertas en menos: borde rozado, no aportan una serie propia
_EPS = 1e-9              # -71.95 / 0.1 = -719.4999999999999: sin tolerancia el empate dependeria del redondeo


# --- rejilla de clima -------------------------------------------------------------

def cuadrante_de(lat, lon):
    """Indices enteros (i, j) del nodo mas cercano. Un punto justo en el borde va a la celda norte/este."""
    return floor(lat / PASO_GRADOS + 0.5 + _EPS), floor(lon / PASO_GRADOS + 0.5 + _EPS)


def nodo(i, j):
    """(lat, lon) del nodo ERA5-Land del cuadrante (i, j)."""
    return round(i * PASO_GRADOS, 6), round(j * PASO_GRADOS, 6)


def id_cuadrante(i, j):
    """Identificador legible y estable, las coordenadas del nodo: '-16.6_-71.9'."""
    lat, lon = nodo(i, j)
    return f"{lat:.1f}_{lon:.1f}"


def poligono_cuadrante(i, j):
    """GeoJSON Polygon de la celda: nodo +/- medio paso, en sentido antihorario."""
    lat, lon = nodo(i, j)
    m = PASO_GRADOS / 2
    s, n = round(lat - m, 6), round(lat + m, 6)
    w, e = round(lon - m, 6), round(lon + m, 6)
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


# --- geocercas ----------------------------------------------------------------------

def partes_geocerca(gj):
    """Anillos exteriores [[lon, lat], ...] (abiertos) de un Polygon o de cada parte de un MultiPolygon."""
    geom = _geometria(gj)
    if geom["type"] == "Polygon":
        poligonos = [geom["coordinates"]]
    elif geom["type"] == "MultiPolygon":
        poligonos = geom["coordinates"]
    else:
        raise ValueError(f"Geometria no soportada para una geocerca: {geom['type']}")
    return [[list(p[:2]) for p in _anillo({"type": "Polygon", "coordinates": c})] for c in poligonos]


def _poligono(anillo):
    return {"type": "Polygon", "coordinates": [[list(p) for p in anillo] + [list(anillo[0])]]}


def area_geocerca_ha(gj):
    """Area total en ha, sumando partes (`calculo.area_ha` solo mide un Polygon)."""
    return sum(area_ha(_poligono(a)) for a in partes_geocerca(gj))


def _cruz(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _en_segmento(px, py, a, b, tol=1e-12):
    if abs(_cruz(a, b, (px, py))) > tol:
        return False
    return (min(a[0], b[0]) - tol <= px <= max(a[0], b[0]) + tol
            and min(a[1], b[1]) - tol <= py <= max(a[1], b[1]) + tol)


def _en_anillo(lat, lon, anillo):
    """Ray casting sobre un anillo abierto; el borde cuenta como dentro."""
    if len(anillo) < 3:
        return False
    dentro = False
    n = len(anillo)
    for k in range(n):
        a, b = anillo[k], anillo[(k + 1) % n]
        if _en_segmento(lon, lat, a, b):
            return True
        if (a[1] > lat) != (b[1] > lat):
            x_corte = a[0] + (lat - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if lon < x_corte:
                dentro = not dentro
    return dentro


def punto_en_geocerca(lat, lon, gj):
    """True si (lat, lon) cae dentro (o sobre el borde) de alguna parte de la geocerca."""
    return any(_en_anillo(lat, lon, a) for a in partes_geocerca(gj))


def _cruzan(p1, p2, p3, p4):
    """Cruce propio de los segmentos p1-p2 y p3-p4 (tocarse en un extremo no cuenta)."""
    return (_cruz(p3, p4, p1) * _cruz(p3, p4, p2) < 0
            and _cruz(p1, p2, p3) * _cruz(p1, p2, p4) < 0)


def anillo_simple(anillo):
    """False si el contorno se cruza a si mismo (un poligono dibujado 'en ocho' no tiene area valida)."""
    n = len(anillo)
    for a in range(n):
        for b in range(a + 2, n):
            if a == 0 and b == n - 1:      # primer y ultimo borde son vecinos por el cierre
                continue
            if _cruzan(anillo[a], anillo[(a + 1) % n], anillo[b], anillo[(b + 1) % n]):
                return False
    return True


def se_solapan(gj_a, gj_b):
    """True si dos geocercas comparten area: bordes que se cruzan o una parte contenida en otra."""
    for x in partes_geocerca(gj_a):
        for y in partes_geocerca(gj_b):
            for i in range(len(x)):
                for j in range(len(y)):
                    if _cruzan(x[i], x[(i + 1) % len(x)], y[j], y[(j + 1) % len(y)]):
                        return True
            if _en_anillo(x[0][1], x[0][0], y) or _en_anillo(y[0][1], y[0][0], x):
                return True
    return False


# --- muestreo climatico -------------------------------------------------------------

def _recortar(anillo, s, w, n, e):
    """Recorte Sutherland-Hodgman del anillo contra el rectangulo [s, n] x [w, e] (anillo abierto)."""
    def corte_lon(x):
        return lambda a, b: [x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])]

    def corte_lat(y):
        return lambda a, b: [a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]), y]

    bordes = (
        (lambda p: p[0] >= w, corte_lon(w)),
        (lambda p: p[0] <= e, corte_lon(e)),
        (lambda p: p[1] >= s, corte_lat(s)),
        (lambda p: p[1] <= n, corte_lat(n)),
    )
    puntos = [list(p) for p in anillo]
    for adentro, cortar in bordes:
        entrada, puntos = puntos, []
        for k, b in enumerate(entrada):
            a = entrada[k - 1]
            if adentro(b):
                if not adentro(a):
                    puntos.append(cortar(a, b))
                puntos.append(b)
            elif adentro(a):
                puntos.append(cortar(a, b))
        if not puntos:
            break
    return puntos


def _punto_interior(anillo, lat):
    """Punto dentro del anillo a la latitud dada: centro del tramo mas ancho de esa horizontal."""
    lats = [p[1] for p in anillo]
    if not min(lats) < lat < max(lats):
        lat = (min(lats) + max(lats)) / 2
    cortes = []
    n = len(anillo)
    for k in range(n):
        a, b = anillo[k], anillo[(k + 1) % n]
        if (a[1] > lat) != (b[1] > lat):
            cortes.append(a[0] + (lat - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
    cortes.sort()
    x0, x1 = max(((cortes[k], cortes[k + 1]) for k in range(0, len(cortes) - 1, 2)),
                 key=lambda t: t[1] - t[0])
    return lat, (x0 + x1) / 2


def muestreo_clima(gj, min_ha=MIN_HA_CUADRANTE, referencias=()):
    """
    Cuadrantes que la geocerca cubre y el punto donde pedir el clima de cada uno.

    `referencias` son puntos (lat, lon) VERIFICADOS sobre cultivo (el usuario los ubico y se
    revisaron sobre satelite). Si alguno cae en la celda y dentro de la geocerca, se usa ese en
    lugar del punto calculado: el centroide de la parte cubierta puede caer en pampa o cerro
    cuando la geocerca abarca terreno sin cultivo.

    Devuelve una lista (ordenada por celda) de dicts: id, nodo_lat, nodo_lon, area_ha (superficie
    de la geocerca dentro de la celda), punto_lat, punto_lon y punto_metodo:
      'referencia' -> punto verificado sobre cultivo (el mas cercano al centro del area cubierta);
      'centroide'  -> centroide de la parte cubierta (ponderado por area si hay varias partes);
      'interior'   -> ese centroide cae fuera de la geocerca (forma concava o partes separadas):
                      se usa un punto interior de la pieza mas grande, a la misma latitud.
    Se descartan celdas cubiertas en menos de `min_ha`, salvo que la geocerca entera sea mas
    chica: entonces queda la celda con mas area, para que toda zona tenga al menos una serie.
    """
    celdas = {}
    m = PASO_GRADOS / 2
    for anillo in partes_geocerca(gj):
        lats = [p[1] for p in anillo]
        lons = [p[0] for p in anillo]
        i0, j0 = cuadrante_de(min(lats), min(lons))
        i1, j1 = cuadrante_de(max(lats), max(lons))
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                lat, lon = nodo(i, j)
                pieza = _recortar(anillo, lat - m, lon - m, lat + m, lon + m)
                if len(pieza) < 3:
                    continue
                ha = area_ha(_poligono(pieza))
                if ha > 0:
                    celdas.setdefault((i, j), []).append((ha, pieza, centroide(_poligono(pieza))))
    if not celdas:
        return []

    def cubierta(clave):
        return sum(p[0] for p in celdas[clave])

    elegidas = [k for k in sorted(celdas) if cubierta(k) >= min_ha] or [max(celdas, key=cubierta)]

    resultado = []
    for i, j in elegidas:
        piezas = celdas[(i, j)]
        total = cubierta((i, j))
        lat_area = sum(ha * c[0] for ha, _, c in piezas) / total
        lon_area = sum(ha * c[1] for ha, _, c in piezas) / total
        verificadas = [r for r in referencias
                       if cuadrante_de(r[0], r[1]) == (i, j) and punto_en_geocerca(r[0], r[1], gj)]
        if verificadas:
            lat, lon = min(verificadas, key=lambda r: (r[0] - lat_area) ** 2 + (r[1] - lon_area) ** 2)
            metodo = "referencia"
        elif punto_en_geocerca(lat_area, lon_area, gj):
            lat, lon, metodo = lat_area, lon_area, "centroide"
        else:
            _, pieza, _ = max(piezas, key=lambda p: p[0])
            lat, lon = _punto_interior(pieza, lat_area)
            metodo = "interior"
        nlat, nlon = nodo(i, j)
        resultado.append({
            "id": id_cuadrante(i, j), "nodo_lat": nlat, "nodo_lon": nlon,
            "area_ha": round(total, 1),
            "punto_lat": round(lat, 6), "punto_lon": round(lon, 6), "punto_metodo": metodo,
        })
    return resultado
