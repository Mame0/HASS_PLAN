"""
Z2: arma la serie de rendimiento de palta a partir de los anuarios de MIDAGRI.

HALLAZGO QUE CONDICIONA Z2 Y Z3 (verificado 17-sep-2026)
--------------------------------------------------------
El dato publico de palta llega SOLO a nivel de REGION. Se comprobo una por una:
  * Compendio anual "Produccion Agricola" (gob.pe): unica fuente descargable. Publica
    "Palta: produccion, superficie cosechada, rendimiento y precio en chacra, SEGUN REGION"
    (Cuadro 480 en 2017-2018, Cuadro 453 desde 2019). Anuarios disponibles: 2016-2023.
  * Portal SIEA: los paneles Power BI son regionales/departamentales; las rutas antiguas de
    descarga (phocadownload/.../anuarios/agricola/agricola_AAAA.pdf) redirigen a la portada.
  * datosabiertos.gob.pe: la API responde `package_list`, pero `package_show` del dataset de
    MIDAGRI devuelve vacio y la ficha web exige iniciar sesion.
  * SISCA (frenteweb.minagri.gob.pe), geosiea e INEI: no responden.
  * agroarequipa.gob.pe: su seccion de estadistica da 404.

=> NO existe serie distrital publica: La Joya y Majes no se pueden separar en el objetivo.
   Este script deja el mejor dato verificable (region x ano) y Z3 decide que unidad usar.

Salidas
-------
    datos/zonas/rendimiento_midagri.csv   una fila por (ano, region)
    datos/zonas/rendimiento_meta.json     anuarios usados, cobertura y avisos de validacion

Uso (desde sistema_palta/)
--------------------------
    python scripts/zonas/rendimiento_midagri.py --descargar   # baja los anuarios que falten
    python scripts/zonas/rendimiento_midagri.py               # arma el CSV desde lo descargado
    python scripts/zonas/rendimiento_midagri.py --region Arequipa   # ademas imprime esa serie
"""
import sys
import os
import re
import json
import argparse
import unicodedata
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")          # consola Windows cp1252 (ver CLAUDE.md)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

import pandas as pd                                                      # noqa: E402
import requests                                                          # noqa: E402

FUENTES = os.path.join(RAIZ, "datos", "zonas", "fuentes", "midagri")
SALIDA_CSV = os.path.join(RAIZ, "datos", "zonas", "rendimiento_midagri.csv")
SALIDA_META = os.path.join(RAIZ, "datos", "zonas", "rendimiento_meta.json")
PAGINA = ("https://www.gob.pe/institucion/midagri/informes-publicaciones/"
          "2730325-compendio-anual-de-produccion-agricola")
CABECERA = {"User-Agent": "Mozilla/5.0"}
COLUMNAS = ["anio", "region", "ambito", "produccion_t", "superficie_cosechada_ha",
            "rendimiento_kg_ha", "rendimiento_t_ha", "precio_chacra_soles_kg",
            "rendimiento_recalculado_kg_ha", "dif_pct", "fuente"]


def descargar():
    """Baja de gob.pe los anuarios que falten (uno por ano) a datos/zonas/fuentes/midagri/."""
    os.makedirs(FUENTES, exist_ok=True)
    html = requests.get(PAGINA, headers=CABECERA, timeout=120).text
    enlaces = sorted(set(re.findall(r'href="([^"]+\.xlsx?)(?:\?[^"]*)?"', html, re.I)))
    bajados = []
    for url in enlaces:
        anio = re.search(r"(20\d\d)", requests.utils.unquote(url.split("/")[-1]))
        if not anio:
            continue
        destino = os.path.join(FUENTES, f"anuario_{anio.group(1)}"
                                        f"{'.xlsx' if url.lower().endswith('x') else '.xls'}")
        if os.path.exists(destino):
            continue
        r = requests.get(url, headers=CABECERA, timeout=300)
        r.raise_for_status()
        with open(destino, "wb") as fh:
            fh.write(r.content)
        bajados.append(os.path.basename(destino))
    print(f"Anuarios descargados: {bajados or 'ninguno nuevo'}")


def sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn")


def normalizar_region(nombre):
    """'Áncash' y 'Ancash' son la misma region; 'Lima Metropolitana' se conserva aparte."""
    limpio = re.sub(r"\s+", " ", sin_tildes(nombre)).strip().strip("*").strip()
    return limpio.title()


def num(v):
    """Numero o None. Los anuarios usan '-' y ' - ' para el dato no disponible."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    texto = str(v).strip().replace(",", "")
    if texto in ("", "-", "--", "n.d.", "nd"):
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _abrir(ruta):
    return pd.ExcelFile(ruta, engine="xlrd" if ruta.lower().endswith(".xls") else "openpyxl")


def leer_tabla_por_region(ruta, anio):
    """
    Formato 2017-2023: hoja 'palta' con una fila por region (Cuadro 480 / 453).

    OJO: la hoja trae DOS tablas, la de produccion mensual (columnas 0-13) y la de region
    (columnas 16-20). Por eso no se leen posiciones fijas: se busca la celda 'Region' y se
    mapean las columnas por su encabezado (Produccion / Superficie / Rendimiento / Precio).
    """
    xl = _abrir(ruta)
    hojas = [h for h in xl.sheet_names if "palt" in h.lower()]
    if not hojas:
        return []
    df = xl.parse(hojas[0], header=None)

    ancla = None
    for i in range(min(20, len(df))):
        for j, v in enumerate(df.iloc[i]):
            if sin_tildes(v).strip().lower() == "region":
                ancla = (i, j)
                break
        if ancla:
            break
    if ancla is None:
        return []
    fila_cab, col_region = ancla

    columnas = {}
    for j, v in enumerate(df.iloc[fila_cab]):
        etiqueta = sin_tildes(v).strip().lower()
        for clave, prefijo in (("produccion_t", "produccion"), ("superficie_cosechada_ha", "superficie"),
                               ("rendimiento_kg_ha", "rendimiento"), ("precio_chacra_soles_kg", "precio")):
            if etiqueta.startswith(prefijo):
                columnas[clave] = j
    if "produccion_t" not in columnas:
        return []

    filas = []
    for _, fila in df.iloc[fila_cab + 1:].iterrows():
        etiqueta = str(fila[col_region]).strip()
        if etiqueta in ("", "nan") or etiqueta.lower().startswith(("fuente", "nota", "1/", "elabora")):
            if filas:                               # fin de la tabla
                break
            continue
        if etiqueta.startswith("("):
            continue                                # fila de unidades: (t), (ha), (kg/ha)
        valores = {k: num(fila[j]) for k, j in columnas.items()}
        if all(v is None for v in valores.values()):
            continue
        filas.append({"anio": anio, "region": normalizar_region(etiqueta),
                      "fuente": os.path.basename(ruta), **valores})
    return filas


def leer_tabla_2016(ruta, anio):
    """Formato 2016: C.63 (superficie cosechada) y C.64 (produccion), productos en columnas."""
    xl = _abrir(ruta)

    def matriz(clave):
        for hoja in xl.sheet_names:
            df = xl.parse(hoja, header=None, nrows=6)
            blob = sin_tildes(" ".join(str(v).lower() for v in df.values.flatten())).lower()
            if "frutas" in blob and clave in blob:
                return xl.parse(hoja, header=None)
        return None

    superficie = matriz("superficie cosechada")
    produccion = matriz("produccion")
    if superficie is None or produccion is None:
        return []

    def columna_palta(df):
        for i in range(min(12, len(df))):
            for j, v in enumerate(df.iloc[i]):
                if sin_tildes(v).strip().lower() == "palta":
                    return i, j
        return None, None

    def serie(df):
        fila_cab, col = columna_palta(df)
        if col is None:
            return {}
        datos = {}
        for _, fila in df.iloc[fila_cab + 1:].iterrows():
            etiqueta = str(fila[0]).strip()
            if etiqueta in ("", "nan") or etiqueta.lower().startswith(("fuente", "nota", "1/")):
                continue
            v = num(fila[col])
            if v is not None:
                datos[normalizar_region(etiqueta)] = v
        return datos

    sup, prod = serie(superficie), serie(produccion)
    filas = []
    for region in sorted(set(sup) & set(prod)):
        ha, t = sup[region], prod[region]
        filas.append({"anio": anio, "region": region, "produccion_t": t,
                      "superficie_cosechada_ha": ha,
                      "rendimiento_kg_ha": (t * 1000 / ha) if ha else None,
                      "precio_chacra_soles_kg": None, "fuente": os.path.basename(ruta)})
    return filas


def construir():
    """Lee todos los anuarios disponibles y devuelve (filas, avisos)."""
    filas, avisos = [], []
    if not os.path.isdir(FUENTES):
        return filas, [f"No existe {os.path.relpath(FUENTES, RAIZ)}; corre con --descargar."]
    for archivo in sorted(os.listdir(FUENTES)):
        m = re.match(r"anuario_(20\d\d)\.(xlsx?|xls)$", archivo, re.I)
        if not m:
            continue
        anio, ruta = int(m.group(1)), os.path.join(FUENTES, archivo)
        try:
            nuevas = leer_tabla_por_region(ruta, anio) or leer_tabla_2016(ruta, anio)
        except Exception as e:                       # un anuario ilegible no debe tumbar el resto
            avisos.append(f"{archivo}: no se pudo leer ({type(e).__name__}: {e}).")
            continue
        if not nuevas:
            avisos.append(f"{archivo}: sin tabla de palta reconocible.")
            continue
        filas.extend(nuevas)
        print(f"  {archivo:22} {len(nuevas):3} filas")

    for f in filas:
        f["ambito"] = "nacional" if f["region"].lower() == "nacional" else "region"
        prod, ha = f["produccion_t"], f["superficie_cosechada_ha"]
        recalculado = (prod * 1000 / ha) if (prod and ha) else None
        f["rendimiento_recalculado_kg_ha"] = round(recalculado, 1) if recalculado else None
        publicado = f["rendimiento_kg_ha"]
        if publicado and recalculado:
            f["dif_pct"] = round(100 * (publicado - recalculado) / recalculado, 2)
        else:
            f["dif_pct"] = None
        if publicado is None and recalculado:
            f["rendimiento_kg_ha"] = round(recalculado, 1)
        f["rendimiento_t_ha"] = round(f["rendimiento_kg_ha"] / 1000, 2) if f["rendimiento_kg_ha"] else None
        for k in ("produccion_t", "superficie_cosechada_ha", "rendimiento_kg_ha", "precio_chacra_soles_kg"):
            if f[k] is not None:
                f[k] = round(f[k], 2)

    descuadres = [f for f in filas if f["dif_pct"] is not None and abs(f["dif_pct"]) > 1]
    if descuadres:
        avisos.append(f"{len(descuadres)} filas donde el rendimiento publicado difiere >1% de "
                      f"produccion/superficie (ej. {descuadres[0]['region']} {descuadres[0]['anio']}: "
                      f"{descuadres[0]['dif_pct']}%).")
    return filas, avisos


def main():
    ap = argparse.ArgumentParser(description="Arma la serie de rendimiento de palta de MIDAGRI (Z2).")
    ap.add_argument("--descargar", action="store_true", help="baja los anuarios que falten")
    ap.add_argument("--region", default="Arequipa", help="region cuya serie se imprime")
    args = ap.parse_args()

    if args.descargar:
        descargar()

    print("Leyendo anuarios de MIDAGRI:")
    filas, avisos = construir()
    if not filas:
        print("Sin datos. Corre con --descargar.")
        for a in avisos:
            print("  AVISO:", a)
        return 1

    df = pd.DataFrame(filas)[COLUMNAS].sort_values(["anio", "region"])
    os.makedirs(os.path.dirname(SALIDA_CSV), exist_ok=True)
    df.to_csv(SALIDA_CSV, index=False, encoding="utf-8")

    anios = sorted(df["anio"].unique())
    regiones = sorted(df[df["ambito"] == "region"]["region"].unique())
    print(f"\n{len(df)} filas · {len(anios)} anos ({anios[0]}-{anios[-1]}) · {len(regiones)} regiones")

    objetivo = normalizar_region(args.region)
    serie = df[df["region"] == objetivo].sort_values("anio")
    if serie.empty:
        print(f"\nSin datos para {objetivo}. Regiones disponibles: {', '.join(regiones[:8])}...")
    else:
        print(f"\nSerie de {objetivo} (la unidad mas fina que existe publicada):")
        print(f"  {'ano':>5}{'produccion t':>14}{'sup. ha':>10}{'t/ha':>8}{'S//kg':>8}")
        for _, f in serie.iterrows():
            precio = f"{f['precio_chacra_soles_kg']:.2f}" if pd.notna(f["precio_chacra_soles_kg"]) else "-"
            print(f"  {int(f['anio']):>5}{f['produccion_t']:>14,.0f}{f['superficie_cosechada_ha']:>10,.0f}"
                  f"{f['rendimiento_t_ha']:>8.1f}{precio:>8}")
        vals = serie["rendimiento_t_ha"].dropna()
        if len(vals) > 1:
            print(f"  media {vals.mean():.1f} t/ha · rango {vals.min():.1f}-{vals.max():.1f} · "
                  f"desviacion {vals.std():.1f}")

    print("\nAVISOS:" if avisos else "\nAVISOS: ninguno")
    for a in avisos:
        print("  -", a)
    print("\nLIMITACION: MIDAGRI publica palta solo por REGION; no hay serie por distrito, "
          "asi que La Joya y Majes comparten el mismo objetivo (ver cabecera del script).")

    with open(SALIDA_META, "w", encoding="utf-8") as fh:
        json.dump({"generado": date.today().isoformat(), "fuente": PAGINA,
                   "anuarios": sorted(df["fuente"].unique().tolist()),
                   "anios": [int(anios[0]), int(anios[-1])], "filas": len(df),
                   "regiones": regiones, "granularidad": "region",
                   "avisos": avisos}, fh, ensure_ascii=False, indent=2)
    for ruta in (SALIDA_CSV, SALIDA_META):
        print(f"Guardado: {os.path.relpath(ruta, RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
