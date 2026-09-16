"""
Z1 (parte 1): descarga el clima historico de cada cuadrante y deriva las 12 variables del modelo.

Entrada: `datos/zonas/muestreo_clima.json` (lo genera `validar_geocercas.py`), con el punto y la
altitud de cada celda ERA5-Land que cubre una geocerca.

Por que era5_seamless fijo
-------------------------
Open-Meteo elige por defecto el mejor modelo disponible, y desde 2017 pasa a ECMWF IFS (9 km): en una
serie larga eso mete un salto artificial justo a mitad del periodo. Se fija entonces un solo reanalisis
para las 26 campanas.

No se usa `era5_land` a secas: verificado el 16-sep-2026, Open-Meteo lo sirve SIN lluvia ni ETO (0 horas
con dato en ambas), y son 2 de las 12 variables del modelo. `era5_seamless` entrega las cuatro y combina
ERA5-Land (0.1 grados) donde existe la variable con ERA5 (0.25 grados) donde no: temperatura y humedad
quedan a 0.1 grados y lluvia/ETO a 0.25.
    -> OJO: a 0.25 grados, cuadrantes vecinos pueden compartir el mismo valor de lluvia y ETO.
       Ademas la lluvia del reanalisis es poco fiable en costa hiperarida (ver validacion de Nepena).

Se envia ademas la `elevation` del punto, que es la que usa Open-Meteo para corregir la temperatura por
altitud: asi el resultado es reproducible.

Ventana de campana
------------------
Campana Y = 1-jul-(Y-1) a 30-jun-Y, la misma convencion de `scripts/ml/entrenar.py`. La cosecha de
Arequipa va de febrero a julio, asi que cae dentro del ano Y.

Las 12 variables se derivan con `app.services.clima.derivar.derivar_features`, la MISMA funcion que usa
la app en produccion (regla de pipeline consistente de CLAUDE.md).

Salidas
-------
    datos/zonas/clima_cuadrantes.csv   una fila por (cuadrante, campana) con las 12 variables
    datos/zonas/clima_zonas.csv        una fila por (zona, campana): promedio ponderado por area cubierta
    datos/zonas/clima_meta.json        modelo, ventana, puntos y fecha de descarga

Uso (desde sistema_palta/)
--------------------------
    python scripts/zonas/clima_zonas.py                      # baja lo que falte (reanuda)
    python scripts/zonas/clima_zonas.py --desde 2010         # solo desde esa campana
    python scripts/zonas/clima_zonas.py --refrescar          # vuelve a bajar todo
    python scripts/zonas/clima_zonas.py --cuadrante -16.6_-71.9 --desde 2024   # prueba corta
"""
import sys
import os
import csv
import json
import argparse
import time
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")          # consola Windows cp1252 (ver CLAUDE.md)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

import requests                                                          # noqa: E402

from app.services.clima.base import SerieHoraria                         # noqa: E402
from app.services.clima.derivar import derivar_features                  # noqa: E402

MUESTREO = os.path.join(RAIZ, "datos", "zonas", "muestreo_clima.json")
CSV_CUADRANTES = os.path.join(RAIZ, "datos", "zonas", "clima_cuadrantes.csv")
CSV_ZONAS = os.path.join(RAIZ, "datos", "zonas", "clima_zonas.csv")
META = os.path.join(RAIZ, "datos", "zonas", "clima_meta.json")

ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
MODELO = "era5_seamless"   # era5_land no trae lluvia ni ETO (ver cabecera)
VARIABLES = "temperature_2m,relative_humidity_2m,precipitation,et0_fao_evapotranspiration"
FEATURES = ["hfrio_19", "hfrio_15", "hfrio_14", "hfrio_14_19", "hac_20_25", "hac_25",
            "t_prom", "t_min", "t_max", "humedad", "lluvia", "eto"]
COLUMNAS = ["zona", "cuadrante", "anio", "punto_lat", "punto_lon", "elevacion_m", "area_ha",
            "horas"] + FEATURES
ANIOS_POR_PEDIDO = 3          # bloques chicos: con 5 anos la API cortaba la conexion a menudo


def ventana(anio):
    """Campana Y = 1-jul-(Y-1) .. 30-jun-Y (igual que scripts/ml/entrenar.py)."""
    return date(anio - 1, 7, 1), date(anio, 6, 30)


def ultima_campana_completa(hoy=None):
    hoy = hoy or date.today()
    return hoy.year if hoy >= date(hoy.year, 7, 1) else hoy.year - 1


def pedir(lat, lon, elevacion, desde, hasta, intentos=3):
    """Serie horaria de Open-Meteo con su eje de tiempo.

    Reintenta con espera creciente: en series de varios anos la API corta conexiones de vez en
    cuando (ConnectionResetError) y perder el bloque significaria quedarse sin esas campanas.
    """
    params = {"latitude": lat, "longitude": lon, "start_date": desde.isoformat(),
              "end_date": hasta.isoformat(), "hourly": VARIABLES, "models": MODELO,
              "timezone": "auto"}
    if elevacion is not None:
        params["elevation"] = elevacion
    for intento in range(1, intentos + 1):
        try:
            r = requests.get(ENDPOINT, params=params, timeout=180)
            if r.status_code >= 400:              # la API explica el motivo en el cuerpo
                raise RuntimeError(f"{r.status_code}: {r.text[:200]}")
            h = r.json().get("hourly") or {}
            if not h.get("time"):
                raise RuntimeError("respuesta sin eje de tiempo")
            return h
        except (requests.RequestException, ValueError) as e:
            if intento == intentos:
                raise RuntimeError(f"{type(e).__name__}: {e}") from e
            time.sleep(2 ** intento)              # 2 s, 4 s


def cortar(horario, desde, hasta):
    """Sub-serie [desde, hasta] (fechas inclusive) a partir del eje 'time' (ISO 'YYYY-MM-DDTHH:MM')."""
    d, h = desde.isoformat(), hasta.isoformat()
    indices = [k for k, t in enumerate(horario["time"]) if d <= t[:10] <= h]
    if not indices:
        return None
    ini, fin = indices[0], indices[-1] + 1
    return SerieHoraria(
        temperatura=horario.get("temperature_2m", [])[ini:fin],
        humedad=horario.get("relative_humidity_2m", [])[ini:fin],
        precipitacion=horario.get("precipitation", [])[ini:fin],
        eto=horario.get("et0_fao_evapotranspiration", [])[ini:fin],
    )


def leer_csv(ruta):
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def escribir_csv(ruta, columnas, filas):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)


def promedio_por_zona(filas):
    """Clima de la zona por campana: promedio de sus cuadrantes ponderado por area cubierta."""
    grupos = {}
    for f in filas:
        grupos.setdefault((f["zona"], int(f["anio"])), []).append(f)
    salida = []
    for (zona, anio), celdas in sorted(grupos.items()):
        fila = {"zona": zona, "anio": anio, "cuadrantes": len(celdas),
                "area_ha": round(sum(float(c["area_ha"]) for c in celdas), 1)}
        for feat in FEATURES:
            pares = [(float(c["area_ha"]), float(c[feat])) for c in celdas
                 if c[feat] not in ("", "None", None)]
            peso = sum(p for p, _ in pares)
            fila[feat] = round(sum(p * v for p, v in pares) / peso, 2) if peso else ""
        salida.append(fila)
    return salida


def volcar(filas):
    """Escribe los tres archivos con lo que haya. Se llama tras CADA cuadrante: si el proceso muere
    (pasa con series largas), la siguiente corrida reanuda desde aqui en vez de empezar de cero."""
    ordenadas = [filas[k] for k in sorted(filas, key=lambda k: (k[0], k[1]))]
    escribir_csv(CSV_CUADRANTES, COLUMNAS, ordenadas)
    zonas = promedio_por_zona(ordenadas)
    escribir_csv(CSV_ZONAS, ["zona", "anio", "cuadrantes", "area_ha"] + FEATURES, zonas)
    return ordenadas, zonas


def main():
    ap = argparse.ArgumentParser(description="Descarga el clima por cuadrante y lo agrega por zona (Z1).")
    ap.add_argument("--muestreo", default=MUESTREO)
    ap.add_argument("--desde", type=int, default=2001, help="primera campana (por defecto 2001)")
    ap.add_argument("--hasta", type=int, default=None, help="ultima campana (por defecto, la ultima completa)")
    ap.add_argument("--cuadrante", action="append", help="limita a estos cuadrantes (repetible)")
    ap.add_argument("--refrescar", action="store_true", help="ignora lo ya descargado")
    args = ap.parse_args()

    if not os.path.exists(args.muestreo):
        print(f"No existe {args.muestreo}. Corre antes: python scripts/zonas/validar_geocercas.py --guardar")
        return 1
    with open(args.muestreo, encoding="utf-8") as fh:
        muestreo = json.load(fh)

    hasta = args.hasta or ultima_campana_completa()
    anios = list(range(args.desde, hasta + 1))
    puntos = [(zona, c) for zona, z in muestreo["zonas"].items() for c in z["cuadrantes"]]
    if args.cuadrante:
        puntos = [(z, c) for z, c in puntos if c["id"] in args.cuadrante]
    if not puntos:
        print("Ningun cuadrante seleccionado.")
        return 1

    previas = [] if args.refrescar else leer_csv(CSV_CUADRANTES)
    hechas = {(f["cuadrante"], int(f["anio"])) for f in previas}
    filas = {(f["cuadrante"], int(f["anio"])): f for f in previas}

    print(f"Modelo {MODELO} · campanas {anios[0]}-{anios[-1]} · {len(puntos)} cuadrantes "
          f"({len(hechas)} filas ya descargadas)")
    sin_eto = []
    for zona, c in puntos:
        pendientes = [a for a in anios if (c["id"], a) not in hechas]
        if not pendientes:
            print(f"  {zona:8} {c['id']:12} al dia")
            continue
        print(f"  {zona:8} {c['id']:12} {len(pendientes)} campanas...", end="", flush=True)
        for k in range(0, len(pendientes), ANIOS_POR_PEDIDO):
            bloque = pendientes[k:k + ANIOS_POR_PEDIDO]
            desde, _ = ventana(bloque[0])
            _, hasta_b = ventana(bloque[-1])
            try:
                horario = pedir(c["punto_lat"], c["punto_lon"], c.get("elevacion_m"), desde, hasta_b)
            except (requests.RequestException, RuntimeError) as e:
                print(f"\n    ERROR {c['id']} {bloque[0]}-{bloque[-1]}: {e}")
                continue
            for anio in bloque:
                serie = cortar(horario, *ventana(anio))
                if serie is None:
                    continue
                try:
                    valores = derivar_features(serie)
                except ValueError as e:                    # sin temperatura no hay nada que derivar
                    print(f"\n    SIN DATOS {c['id']} {anio}: {e}")
                    continue
                if valores.get("eto") is None:
                    sin_eto.append((c["id"], anio))
                filas[(c["id"], anio)] = {
                    "zona": zona, "cuadrante": c["id"], "anio": anio,
                    "punto_lat": c["punto_lat"], "punto_lon": c["punto_lon"],
                    "elevacion_m": c.get("elevacion_m", ""), "area_ha": c["area_ha"],
                    "horas": serie.horas(),
                    **{f: valores.get(f) for f in FEATURES},
                }
            print(".", end="", flush=True)
        ordenadas, zonas = volcar(filas)          # guarda lo que va, por si el proceso muere
        print(f" ok ({len(ordenadas)} filas)")

    ordenadas, zonas = volcar(filas)
    with open(META, "w", encoding="utf-8") as fh:
        json.dump({"generado": date.today().isoformat(), "modelo": MODELO, "endpoint": ENDPOINT,
                   "ventana": "1-jul(Y-1) a 30-jun(Y)", "campanas": [anios[0], anios[-1]],
                   "cuadrantes": sorted({f["cuadrante"] for f in ordenadas}),
                   "filas": len(ordenadas), "variables": FEATURES}, fh, ensure_ascii=False, indent=2)

    print(f"\n{len(ordenadas)} filas de cuadrante-campana · {len(zonas)} filas de zona-campana")
    if sin_eto:
        print(f"AVISO: {len(sin_eto)} filas sin ETO (ERA5-Land no la entrego). Ej: {sin_eto[:3]}")
    for ruta in (CSV_CUADRANTES, CSV_ZONAS, META):
        print(f"Guardado: {os.path.relpath(ruta, RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
