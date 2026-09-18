"""
Z3 (paso 2): clima historico de cada region paltera, con el MISMO pipeline de Z1.

Lee los puntos elegidos por `puntos_regiones.py` y, para cada campana, deriva las 12 variables
del modelo con `app.services.clima.derivar.derivar_features` (la funcion de produccion).
Reutiliza el motor de `clima_zonas.py`: mismo modelo de reanalisis (`era5_seamless`), misma
ventana de campana (1-jul-(Y-1) a 30-jun-Y), mismos reintentos y guardado incremental.

El clima de la region es el promedio simple de sus puntos: a diferencia de las geocercas de
Arequipa, aqui no hay superficie cubierta que sirva de peso.

Salidas
-------
    datos/zonas/clima_regiones_puntos.csv   una fila por (region, punto, campana)
    datos/zonas/clima_regiones.csv          una fila por (region, campana)

Uso (desde sistema_palta/)
--------------------------
    python scripts/zonas/clima_regiones.py                 # baja lo que falte (reanuda)
    python scripts/zonas/clima_regiones.py --desde 2015 --hasta 2024
    python scripts/zonas/clima_regiones.py --region Ica
"""
import sys
import os
import json
import argparse

sys.stdout.reconfigure(encoding="utf-8")          # consola Windows cp1252 (ver CLAUDE.md)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests                                                          # noqa: E402

import clima_zonas as cz                                                 # noqa: E402
from app.services.clima.derivar import derivar_features                  # noqa: E402

PUNTOS = os.path.join(RAIZ, "datos", "zonas", "puntos_regiones.json")
CSV_PUNTOS = os.path.join(RAIZ, "datos", "zonas", "clima_regiones_puntos.csv")
CSV_REGIONES = os.path.join(RAIZ, "datos", "zonas", "clima_regiones.csv")
COLUMNAS = ["region", "punto", "anio", "lat", "lon", "elevacion_m", "horas"] + cz.FEATURES


def promedio_por_region(filas):
    """Clima de la region por campana: promedio simple de sus puntos."""
    grupos = {}
    for f in filas:
        grupos.setdefault((f["region"], int(f["anio"])), []).append(f)
    salida = []
    for (region, anio), puntos in sorted(grupos.items()):
        fila = {"region": region, "anio": anio, "puntos": len(puntos)}
        for feat in cz.FEATURES:
            vals = [float(p[feat]) for p in puntos if p[feat] not in ("", "None", None)]
            fila[feat] = round(sum(vals) / len(vals), 2) if vals else ""
        salida.append(fila)
    return salida


def volcar(filas):
    ordenadas = [filas[k] for k in sorted(filas, key=lambda k: (k[0], k[1], k[2]))]
    cz.escribir_csv(CSV_PUNTOS, COLUMNAS, ordenadas)
    regiones = promedio_por_region(ordenadas)
    cz.escribir_csv(CSV_REGIONES, ["region", "anio", "puntos"] + cz.FEATURES, regiones)
    return ordenadas, regiones


def main():
    ap = argparse.ArgumentParser(description="Clima historico por region paltera (Z3).")
    ap.add_argument("--puntos", default=PUNTOS)
    ap.add_argument("--desde", type=int, default=2014, help="primera campana (2016 es la primera con objetivo)")
    ap.add_argument("--hasta", type=int, default=2024)
    ap.add_argument("--region", action="append", help="limita a estas regiones (repetible)")
    ap.add_argument("--refrescar", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.puntos):
        print(f"No existe {args.puntos}. Corre antes: python scripts/zonas/puntos_regiones.py")
        return 1
    with open(args.puntos, encoding="utf-8") as fh:
        catalogo = json.load(fh)["regiones"]

    anios = list(range(args.desde, args.hasta + 1))
    # Solo puntos verificados sobre cultivo (campo `apto` que deja puntos_regiones.py tras la
    # revision visual): un punto sobre pueblo o cerro daria un clima que no es el del cultivo.
    tareas = [(region, p) for region, ps in catalogo.items() for p in ps
              if p.get("apto", True) and (not args.region or region in args.region)]
    if not tareas:
        print("Ninguna region seleccionada.")
        return 1

    previas = [] if args.refrescar else cz.leer_csv(CSV_PUNTOS)
    filas = {(f["region"], f["punto"], int(f["anio"])): f for f in previas}
    hechas = set(filas)

    print(f"Modelo {cz.MODELO} · campanas {anios[0]}-{anios[-1]} · {len(tareas)} puntos "
          f"({len(hechas)} filas ya descargadas)")
    for region, p in tareas:
        nombre = p.get("zona") or p.get("nombre")
        pendientes = [a for a in anios if (region, nombre, a) not in hechas]
        if not pendientes:
            print(f"  {region:<13} {nombre:<18} al dia")
            continue
        print(f"  {region:<13} {nombre:<18} {len(pendientes)} campanas...", end="", flush=True)
        for k in range(0, len(pendientes), cz.ANIOS_POR_PEDIDO):
            bloque = pendientes[k:k + cz.ANIOS_POR_PEDIDO]
            desde, _ = cz.ventana(bloque[0])
            _, hasta = cz.ventana(bloque[-1])
            try:
                horario = cz.pedir(p["lat"], p["lon"], p.get("elevacion_m"), desde, hasta)
            except (requests.RequestException, RuntimeError) as e:
                print(f"\n    ERROR {region}/{nombre} {bloque[0]}-{bloque[-1]}: {e}")
                continue
            for anio in bloque:
                serie = cz.cortar(horario, *cz.ventana(anio))
                if serie is None:
                    continue
                try:
                    valores = derivar_features(serie)
                except ValueError as e:
                    print(f"\n    SIN DATOS {region}/{nombre} {anio}: {e}")
                    continue
                filas[(region, nombre, anio)] = {
                    "region": region, "punto": nombre, "anio": anio,
                    "lat": p["lat"], "lon": p["lon"], "elevacion_m": p.get("elevacion_m", ""),
                    "horas": serie.horas(), **{f: valores.get(f) for f in cz.FEATURES}}
            print(".", end="", flush=True)
        ordenadas, _ = volcar(filas)              # guarda tras cada punto
        print(f" ok ({len(ordenadas)} filas)")

    ordenadas, regiones = volcar(filas)
    print(f"\n{len(ordenadas)} filas punto-campana · {len(regiones)} filas region-campana")
    for ruta in (CSV_PUNTOS, CSV_REGIONES):
        print(f"Guardado: {os.path.relpath(ruta, RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
