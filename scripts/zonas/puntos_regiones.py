"""
Z3 (paso 1): elige DONDE pedir el clima de cada region paltera, con un criterio objetivo.

Por que no sirve "un punto a ojo"
---------------------------------
Una region es enorme y su clima cambia con la altitud. Si el punto cae en el pueblo, el cerro o
el desierto, el clima no representa al cultivo (Open-Meteo corrige la temperatura por la altitud
del punto pedido). En la revision visual de los candidatos iniciales, la mitad caia fuera de campo.

Criterio (reproducible)
-----------------------
Para cada region se consulta OpenStreetMap (Overpass) por los poligonos de cultivo
(`landuse=farmland|orchard`) dentro del area productora conocida, y se toma la **mediana** de sus
centros: un punto robusto que cae dentro de la mancha agricola y no depende del ojo de nadie.
Si OSM no tiene cobertura ahi, queda el candidato de referencia, marcado como tal.

La zona productora de cada region (la caja de busqueda) SI es conocimiento previo: son los valles
donde se concentra el palto (Viru-Chao, Huaral-Canete, Villacuri-Chincha, Olmos-Motupe...). Cada
punto elegido se verifica despues sobre satelite y con su altitud.

Salida: datos/zonas/puntos_regiones.json (entrada de clima_regiones.py)

Uso (desde sistema_palta/)
--------------------------
    python scripts/zonas/puntos_regiones.py            # elige los puntos y guarda el JSON
    python scripts/zonas/puntos_regiones.py --region Ica
"""
import sys
import os
import json
import time
import argparse
from datetime import date
from statistics import median

sys.stdout.reconfigure(encoding="utf-8")          # consola Windows cp1252 (ver CLAUDE.md)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

import requests                                                          # noqa: E402

SALIDA = os.path.join(RAIZ, "datos", "zonas", "puntos_regiones.json")
OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass.openstreetmap.ru/api/interpreter"]
CABECERA = {"User-Agent": "tesis-palta/1.0 (Track Z)"}
RADIO = 0.12          # grados alrededor del candidato (~13 km) para buscar cultivo

# Valles palteros de cada region (referencia) y cuantas zonas se muestrean.
ZONAS_PRODUCTORAS = {
    "La Libertad": [("Viru", -8.412, -78.752), ("Chao", -8.560, -78.686)],
    "Lima":        [("Huaral-Chancay", -11.500, -77.210), ("Canete", -13.077, -76.383)],
    "Ica":         [("Villacuri-Salas", -14.000, -75.790), ("Chincha", -13.450, -76.130)],
    "Lambayeque":  [("Olmos", -5.990, -79.750), ("Motupe", -6.150, -79.710)],
    "Junin":       [("Pichanaki", -10.930, -74.870), ("Chanchamayo", -11.050, -75.320)],
    "Ancash":      [("Nepena", -9.160, -78.430), ("Casma", -9.470, -78.300)],
    "Ayacucho":    [("Luricocha-Huanta", -12.930, -74.250), ("Valle de Ayacucho", -13.130, -74.230)],
    "Arequipa":    [("La Joya", -16.573, -71.927), ("Majes", -16.384, -72.184)],
    "Moquegua":    [("Valle de Moquegua", -17.190, -70.930), ("Omate", -16.680, -70.980)],
    "Apurimac":    [("Curahuasi", -13.550, -72.730), ("Abancay", -13.630, -72.880)],
}
# Arequipa ya tiene sus puntos verificados en muestreo_clima.json (geocercas de Z0).
MUESTREO_AREQUIPA = os.path.join(RAIZ, "datos", "zonas", "muestreo_clima.json")


def overpass(consulta, intentos=4):
    """Consulta Overpass rotando espejos: el publico suele responder 504 en el primer intento."""
    for intento in range(intentos):
        servidor = OVERPASS[intento % len(OVERPASS)]
        try:
            r = requests.post(servidor, data={"data": consulta}, headers=CABECERA, timeout=120)
            if r.status_code == 200:
                return r.json().get("elements", [])
        except requests.RequestException:
            pass
        time.sleep(3 * (intento + 1))
    return None


def centro_cultivos(lat, lon, radio=RADIO):
    """(lat, lon, n) mediana de los centros de los poligonos de cultivo alrededor del candidato."""
    caja = f"{lat - radio},{lon - radio},{lat + radio},{lon + radio}"
    consulta = ('[out:json][timeout:60];('
                f'way["landuse"~"^(farmland|orchard)$"]({caja});'
                f'relation["landuse"~"^(farmland|orchard)$"]({caja});'
                ');out tags center 2000;')
    elementos = overpass(consulta)
    if not elementos:
        return None, None, 0
    centros = [(e["center"]["lat"], e["center"]["lon"]) for e in elementos if "center" in e]
    if not centros:
        return None, None, 0
    return round(median(c[0] for c in centros), 6), round(median(c[1] for c in centros), 6), len(centros)


def elevaciones(puntos):
    r = requests.get("https://api.open-meteo.com/v1/elevation", timeout=60, params={
        "latitude": ",".join(str(p[0]) for p in puntos),
        "longitude": ",".join(str(p[1]) for p in puntos)}, headers=CABECERA)
    r.raise_for_status()
    return [round(e) for e in r.json()["elevation"]]


def puntos_de_arequipa():
    """Reusa los puntos ya verificados de las geocercas (Z0): no se vuelven a elegir."""
    if not os.path.exists(MUESTREO_AREQUIPA):
        return []
    with open(MUESTREO_AREQUIPA, encoding="utf-8") as fh:
        muestreo = json.load(fh)
    salida = []
    for zona, datos in muestreo["zonas"].items():
        # Preferir una celda cuyo punto salga de una REFERENCIA verificada sobre cultivo; entre
        # esas, la de mas superficie. La celda mas grande de La Joya es casi toda pampa: su punto
        # calculado cae fuera de campo y daria un clima que no representa al cultivo.
        verificadas = [c for c in datos["cuadrantes"] if c.get("punto_metodo") == "referencia"]
        mejor = max(verificadas or datos["cuadrantes"], key=lambda c: c["area_ha"])
        salida.append({"zona": zona, "nombre": f"geocerca {zona}", "lat": mejor["punto_lat"],
                       "lon": mejor["punto_lon"],
                       "metodo": "geocerca_z0_referencia" if verificadas else "geocerca_z0",
                       "n_poligonos_osm": None, "elevacion_m": mejor.get("elevacion_m")})
    return salida


def main():
    ap = argparse.ArgumentParser(description="Elige el punto de clima de cada region paltera (Z3).")
    ap.add_argument("--region", action="append", help="limita a estas regiones (repetible)")
    ap.add_argument("--radio", type=float, default=RADIO, help="grados alrededor del valle de referencia")
    args = ap.parse_args()

    regiones = {r: z for r, z in ZONAS_PRODUCTORAS.items()
                if not args.region or r in args.region}
    resultado = {}
    for region, zonas in regiones.items():
        if region == "Arequipa":
            puntos = puntos_de_arequipa()
            if puntos:
                resultado[region] = puntos
                print(f"{region:<13} {len(puntos)} puntos de las geocercas ya verificadas (Z0)")
                continue
        puntos = []
        for nombre, lat, lon in zonas:
            plat, plon, n = centro_cultivos(lat, lon, args.radio)
            if plat is None:                        # OSM no siempre mapea el valle: ampliar y reintentar
                time.sleep(1.5)
                plat, plon, n = centro_cultivos(lat, lon, args.radio * 2)
            if plat is None:
                puntos.append({"zona": nombre, "nombre": nombre, "lat": lat, "lon": lon,
                               "metodo": "referencia_sin_osm", "n_poligonos_osm": 0})
                print(f"{region:<13} {nombre:<18} SIN cultivo en OSM -> queda el candidato")
            else:
                puntos.append({"zona": nombre, "nombre": nombre, "lat": plat, "lon": plon,
                               "metodo": "mediana_osm", "n_poligonos_osm": n})
                print(f"{region:<13} {nombre:<18} {n:>4} poligonos -> ({plat:.4f}, {plon:.4f})")
            time.sleep(1.5)                     # cortesia con Overpass
        resultado[region] = puntos

    todos = [(p["lat"], p["lon"]) for ps in resultado.values() for p in ps]
    try:
        alturas = elevaciones(todos)
        for p, e in zip((p for ps in resultado.values() for p in ps), alturas):
            p.setdefault("elevacion_m", e)
            if p.get("elevacion_m") is None:
                p["elevacion_m"] = e
    except requests.RequestException as e:
        print(f"AVISO: sin altitudes ({e})")

    anterior = {}
    if os.path.exists(SALIDA):
        with open(SALIDA, encoding="utf-8") as fh:
            anterior = json.load(fh).get("regiones", {})
    anterior.update(resultado)
    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump({"generado": date.today().isoformat(),
                   "criterio": "mediana de los centros de poligonos landuse=farmland|orchard (OSM) "
                               "en el valle paltero de la region; Arequipa usa las geocercas de Z0",
                   "radio_grados": args.radio, "regiones": anterior}, fh, ensure_ascii=False, indent=2)
    n = sum(len(v) for v in anterior.values())
    print(f"\n{n} puntos en {len(anterior)} regiones · Guardado: {os.path.relpath(SALIDA, RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
