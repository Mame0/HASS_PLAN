"""
Valida las geocercas dibujadas a mano (Track Z, fase Z0) y calcula donde se pedira el clima (entrada de Z1).

Errores (bloquean): estructura, zonas del catalogo, contornos que se cruzan, zonas solapadas.
Avisos: partes chicas, referencias de cultivo que la geocerca no cubre o que caen en otra zona.

Muestreo climatico: la geocerca se corta con la rejilla de 0.1 grados de ERA5-Land; cada celda
cubierta aporta un punto DENTRO de la geocerca (ver app/services/geo/zonas.py) y su altitud, que
es la que Open-Meteo usa para corregir la temperatura.

Uso (desde sistema_palta/)
--------------------------
    python scripts/zonas/validar_geocercas.py                  # valida y muestra el muestreo
    python scripts/zonas/validar_geocercas.py --guardar        # ademas escribe datos/zonas/muestreo_clima.json
    python scripts/zonas/validar_geocercas.py --sin-elevacion  # sin consultar la altitud (sin red)
"""
import sys
import os
import json
import argparse
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")          # consola Windows cp1252 (ver CLAUDE.md)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

import requests                                                          # noqa: E402

from app.services.geo.zonas import (                                     # noqa: E402
    MIN_HA_CUADRANTE, partes_geocerca, area_geocerca_ha, anillo_simple, se_solapan,
    punto_en_geocerca, muestreo_clima,
)

# Una zona = una serie de rendimiento distrital MIDAGRI (decision 10-sep-2026).
CATALOGO = {
    "la_joya": {"nombre": "La Joya", "provincia": "Arequipa", "distrito_midagri": "La Joya",
                "unidad_objetivo": "la_joya"},
    "majes": {"nombre": "Majes", "provincia": "Caylloma", "distrito_midagri": "Majes",
              "unidad_objetivo": "majes"},
}
PARTE_MIN_HA = 300          # igual que scripts/zonas/geocercas.html
ARCHIVO = os.path.join(RAIZ, "datos", "zonas", "geocercas.geojson")
REFERENCIAS = os.path.join(RAIZ, "datos", "zonas", "referencias_cultivo.geojson")
SALIDA = os.path.join(RAIZ, "datos", "zonas", "muestreo_clima.json")
ELEVACION = "https://api.open-meteo.com/v1/elevation"      # DEM de 90 m, el mismo del downscaling


def validar(gj):
    """(errores, avisos, {zona: geometria}) de la FeatureCollection de geocercas."""
    errores, avisos, zonas = [], [], {}
    if gj.get("type") != "FeatureCollection":
        return ["El archivo no es un FeatureCollection."], avisos, zonas

    for f in gj.get("features", []):
        p = f.get("properties") or {}
        zid = p.get("id")
        if zid not in CATALOGO:
            errores.append(f"Zona desconocida: {zid!r} (validas: {', '.join(CATALOGO)}).")
            continue
        if zid in zonas:
            errores.append(f"Zona repetida: {zid}.")
            continue
        distintas = [k for k, v in CATALOGO[zid].items() if p.get(k) != v]
        if distintas:
            errores.append(f"{zid}: propiedades distintas del catalogo ({', '.join(distintas)}).")

        geom = f.get("geometry") or {}
        try:
            anillos = partes_geocerca(geom)
        except (ValueError, KeyError, TypeError, IndexError) as e:
            errores.append(f"{zid}: geometria invalida ({e}).")
            continue
        validas = True
        for k, a in enumerate(anillos, 1):
            if len(a) < 3:
                errores.append(f"{zid} parte {k}: menos de 3 vertices.")
                validas = False
                continue
            if not anillo_simple(a):
                errores.append(f"{zid} parte {k}: el contorno se cruza a si mismo.")
                validas = False
            ha = area_geocerca_ha({"type": "Polygon", "coordinates": [a + [a[0]]]})
            if ha < PARTE_MIN_HA:
                avisos.append(f"{zid} parte {k}: {ha:.0f} ha (< {PARTE_MIN_HA}); ¿cubre todo el bloque agricola?")
        if validas:
            zonas[zid] = geom

    for zid in CATALOGO:
        if zid not in zonas and not any(zid in e for e in errores):
            errores.append(f"Falta la zona {zid}.")
    ids = sorted(zonas)
    for x, a in enumerate(ids):
        for b in ids[x + 1:]:
            if se_solapan(zonas[a], zonas[b]):
                errores.append(f"Las zonas {a} y {b} se solapan.")
    return errores, avisos, zonas


def cargar_referencias(ruta):
    """[(zona, id, lat, lon)] de los puntos de cultivo VERIFICADOS; None si no hay archivo.

    Son los puntos que el usuario ubico sobre el satelite; los marcados `sobre_cultivo: false`
    (revisados y descartados) no se usan ni para cobertura ni como punto de clima.
    """
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as fh:
        rasgos = json.load(fh)["features"]
    return [(p["zona"], p["id"], p["punto_lat"], p["punto_lon"])
            for p in (f["properties"] for f in rasgos) if p.get("sobre_cultivo", True)]


def revisar_referencias(zonas, referencias):
    """Avisos: referencias que su geocerca no cubre, o que caen dentro de otra zona."""
    avisos = []
    for zona, rid, lat, lon in referencias:
        if zona not in zonas:
            continue
        if not punto_en_geocerca(lat, lon, zonas[zona]):
            avisos.append(f"{zona}: la geocerca no cubre la referencia de cultivo {rid} ({lat:.4f}, {lon:.4f}).")
        for otra, geom in zonas.items():
            if otra != zona and punto_en_geocerca(lat, lon, geom):
                avisos.append(f"La referencia {rid} de {zona} cae dentro de {otra}.")
    return avisos


def elevaciones(puntos):
    """Altitud (m) de cada (lat, lon) segun Open-Meteo. Hasta 100 puntos por consulta."""
    alturas = []
    for k in range(0, len(puntos), 100):
        lote = puntos[k:k + 100]
        r = requests.get(ELEVACION, timeout=30, params={
            "latitude": ",".join(str(p[0]) for p in lote),
            "longitude": ",".join(str(p[1]) for p in lote)})
        r.raise_for_status()
        alturas.extend(round(e) for e in r.json()["elevation"])
    return alturas


def main():
    ap = argparse.ArgumentParser(description="Valida geocercas y calcula el muestreo climatico (Track Z).")
    ap.add_argument("--archivo", default=ARCHIVO)
    ap.add_argument("--referencias", default=REFERENCIAS)
    ap.add_argument("--min-ha", type=float, default=MIN_HA_CUADRANTE,
                    help="area minima cubierta para que una celda aporte serie (ha)")
    ap.add_argument("--sin-elevacion", action="store_true")
    ap.add_argument("--guardar", action="store_true", help=f"escribe {os.path.relpath(SALIDA, RAIZ)}")
    args = ap.parse_args()

    if not os.path.exists(args.archivo):
        print(f"No existe {args.archivo}. Dibuja las geocercas con scripts/zonas/geocercas.html.")
        return 1
    with open(args.archivo, encoding="utf-8") as fh:
        gj = json.load(fh)

    errores, avisos, zonas = validar(gj)
    referencias = cargar_referencias(args.referencias)
    if referencias is None:
        referencias = []
        avisos.append(f"Sin archivo de referencias ({os.path.relpath(args.referencias, RAIZ)}): "
                      "no se revisa la cobertura ni se usan como punto de clima.")
    elif zonas and not errores:
        avisos += revisar_referencias(zonas, referencias)

    resultado = {}
    if not errores:
        todos = []
        for zid, geom in zonas.items():
            propias = [(lat, lon) for zona, _, lat, lon in referencias if zona == zid]
            celdas = muestreo_clima(geom, args.min_ha, propias)
            resultado[zid] = {**CATALOGO[zid], "partes": len(partes_geocerca(geom)),
                              "area_ha": round(area_geocerca_ha(geom), 1), "cuadrantes": celdas}
            todos.extend(celdas)
        if not args.sin_elevacion and todos:
            try:
                for c, e in zip(todos, elevaciones([(c["punto_lat"], c["punto_lon"]) for c in todos])):
                    c["elevacion_m"] = e
            except requests.RequestException as e:
                avisos.append(f"No se pudo consultar la altitud ({e}); usa --sin-elevacion o reintenta.")

    print(f"== Geocercas: {os.path.relpath(args.archivo, RAIZ)} ==")
    for zid, z in resultado.items():
        print(f"\n{zid}: {z['partes']} parte(s) · {z['area_ha']:,.0f} ha · {len(z['cuadrantes'])} cuadrante(s) de clima")
        print(f"  {'cuadrante':<13}{'ha cubiertas':>13}   {'punto de clima':<24}{'metodo':<11}{'altitud':>8}")
        for c in z["cuadrantes"]:
            alt = f"{c['elevacion_m']} m" if "elevacion_m" in c else "-"
            punto = f"({c['punto_lat']:.4f}, {c['punto_lon']:.4f})"
            print(f"  {c['id']:<13}{c['area_ha']:>13,.0f}   {punto:<24}{c['punto_metodo']:<11}{alt:>8}")
    print("\nAVISOS:" if avisos else "\nAVISOS: ninguno")
    for a in avisos:
        print(f"  - {a}")
    print("ERRORES:" if errores else "ERRORES: ninguno")
    for e in errores:
        print(f"  - {e}")

    if errores:
        return 1
    if args.guardar:
        salida = {
            "generado": date.today().isoformat(),
            "geocercas": os.path.relpath(args.archivo, RAIZ).replace("\\", "/"),
            "min_ha_cuadrante": args.min_ha,
            "rejilla": "ERA5-Land 0.1 grados (Open-Meteo models=era5_land)",
            "zonas": resultado,
        }
        os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
        with open(SALIDA, "w", encoding="utf-8") as fh:
            json.dump(salida, fh, ensure_ascii=False, indent=2)
        print(f"\nGuardado: {os.path.relpath(SALIDA, RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
