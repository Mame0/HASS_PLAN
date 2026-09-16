"""
Z1 (parte 2): contrasta la hipotesis H1 — ¿las zonas tienen climas distintos?

H1: las zonas difieren entre si MAS de lo que cada una varia por dentro (entre anos y entre sus
propios cuadrantes). Si no, agrupar por zona no aporta informacion climatica y la premisa del asesor
no se sostiene, por mucho que el mapa las separe.

Criterio de aceptacion (FIJADO ANTES DE VER LOS RESULTADOS)
-----------------------------------------------------------
Variables clave: hfrio_19, hac_25, eto, humedad, t_min (las que gobiernan la fenologia del palto).
Una variable "separa" si cumple las dos condiciones:
  1. |d| >= 1.0   con d = (media_A - media_B) / SD interanual combinada  -> la brecha entre zonas es
     mayor que lo que cada zona se mueve de una campana a otra;
  2. |media_A - media_B| > dispersion espacial media dentro de las zonas -> la brecha entre zonas es
     mayor que la que ya existe entre cuadrantes de una misma zona.
H1 SE CUMPLE si separan al menos 3 de las 5 variables clave.

Ademas se reporta, por variable: el test pareado por campana (Wilcoxon), la correlacion entre las
series anuales de ambas zonas (si es alta, la diferencia es un desnivel fijo y no un comportamiento
distinto ano a ano) y si la zona cae fuera del rango de entrenamiento del modelo de Nepena (OOD).

Entradas: datos/zonas/clima_zonas.csv y clima_cuadrantes.csv (los genera clima_zonas.py).
Salida:   datos/zonas/separabilidad.json (+ separabilidad.png si hay matplotlib).

Uso (desde sistema_palta/)
--------------------------
    python scripts/zonas/separabilidad.py
    python scripts/zonas/separabilidad.py --desde 2010     # solo campanas recientes
"""
import sys
import os
import csv
import json
import argparse
from statistics import mean, pstdev, stdev
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")          # consola Windows cp1252 (ver CLAUDE.md)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

CSV_ZONAS = os.path.join(RAIZ, "datos", "zonas", "clima_zonas.csv")
CSV_CUADRANTES = os.path.join(RAIZ, "datos", "zonas", "clima_cuadrantes.csv")
META_MODELO = os.path.join(RAIZ, "app", "ml", "modelo_meta.json")
SALIDA = os.path.join(RAIZ, "datos", "zonas", "separabilidad.json")
FIGURA = os.path.join(RAIZ, "datos", "zonas", "separabilidad.png")

FEATURES = ["hfrio_19", "hfrio_15", "hfrio_14", "hfrio_14_19", "hac_20_25", "hac_25",
            "t_prom", "t_min", "t_max", "humedad", "lluvia", "eto"]
CLAVE = ["hfrio_19", "hac_25", "eto", "humedad", "t_min"]
D_MINIMO = 1.0
CLAVES_NECESARIAS = 3


def leer(ruta):
    with open(ruta, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def series_por_zona(filas, desde, hasta):
    """{zona: {anio: {feature: valor}}} de las campanas en rango."""
    salida = {}
    for f in filas:
        anio = int(f["anio"])
        if desde <= anio <= hasta:
            salida.setdefault(f["zona"], {})[anio] = {k: num(f[k]) for k in FEATURES}
    return salida


def dispersion_espacial(cuadrantes, desde, hasta):
    """{zona: {feature: SD media entre cuadrantes dentro de una misma campana}}."""
    porzona = {}
    for f in cuadrantes:
        anio = int(f["anio"])
        if desde <= anio <= hasta:
            porzona.setdefault(f["zona"], {}).setdefault(anio, []).append(f)
    salida = {}
    for zona, anios in porzona.items():
        salida[zona] = {}
        for feat in FEATURES:
            sds = []
            for celdas in anios.values():
                vals = [num(c[feat]) for c in celdas]
                vals = [v for v in vals if v is not None]
                if len(vals) > 1:
                    sds.append(stdev(vals))
            salida[zona][feat] = mean(sds) if sds else 0.0
    return salida


def wilcoxon_pareado(a, b):
    """p-valor aproximado del test de rangos con signo (normal con correccion de continuidad)."""
    difs = [x - y for x, y in zip(a, b) if x is not None and y is not None and x != y]
    n = len(difs)
    if n < 6:
        return None
    orden = sorted(range(n), key=lambda k: abs(difs[k]))
    rangos = [0.0] * n
    k = 0
    while k < n:                                   # rangos promedio en empates
        j = k
        while j + 1 < n and abs(difs[orden[j + 1]]) == abs(difs[orden[k]]):
            j += 1
        promedio = (k + j) / 2 + 1
        for t in range(k, j + 1):
            rangos[orden[t]] = promedio
        k = j + 1
    w_mas = sum(r for r, d in zip(rangos, difs) if d > 0)
    w_menos = sum(r for r, d in zip(rangos, difs) if d < 0)
    w = min(w_mas, w_menos)
    mu = n * (n + 1) / 4
    sigma = (n * (n + 1) * (2 * n + 1) / 24) ** 0.5
    if sigma == 0:
        return None
    z = (abs(w - mu) - 0.5) / sigma
    # cola normal por aproximacion de Zelen & Severo (error < 7.5e-8), sin scipy
    t = 1 / (1 + 0.2316419 * z)
    fi = (2.718281828459045 ** (-z * z / 2)) / (2 * 3.141592653589793) ** 0.5
    cola = fi * (0.319381530 * t - 0.356563782 * t ** 2 + 1.781477937 * t ** 3
                 - 1.821255978 * t ** 4 + 1.330274429 * t ** 5)
    return round(min(1.0, 2 * cola), 4)


def correlacion(a, b):
    pares = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pares) < 3:
        return None
    xs, ys = zip(*pares)
    mx, my = mean(xs), mean(ys)
    num_ = sum((x - mx) * (y - my) for x, y in pares)
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return round(num_ / den, 3) if den else None


def ood_vs_nepena(medias):
    """Por zona y variable: si la media de la zona cae fuera del rango con que se entreno el modelo."""
    if not os.path.exists(META_MODELO):
        return {}
    with open(META_MODELO, encoding="utf-8") as fh:
        rangos = json.load(fh).get("rangos_entrenamiento", {})
    fuera = {}
    for zona, vals in medias.items():
        fuera[zona] = []
        for feat, v in vals.items():
            r = rangos.get(feat)
            if r and v is not None and not r[0] <= v <= r[1]:
                fuera[zona].append({"variable": feat, "media": round(v, 2), "rango": r,
                                    "posicion": "debajo" if v < r[0] else "encima"})
    return fuera


def figura(series, zonas, ruta):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    fig, ejes = plt.subplots(1, len(CLAVE), figsize=(3.2 * len(CLAVE), 3.6))
    for eje, feat in zip(ejes, CLAVE):
        datos = [[series[z][a][feat] for a in sorted(series[z]) if series[z][a][feat] is not None]
                 for z in zonas]
        eje.boxplot(datos, tick_labels=zonas)
        eje.set_title(feat)
        eje.grid(alpha=0.3)
    fig.suptitle("Clima por zona y campaña (variables clave)")
    fig.tight_layout()
    fig.savefig(ruta, dpi=140)
    return ruta


def main():
    ap = argparse.ArgumentParser(description="Contrasta H1: ¿las zonas difieren climaticamente? (Z1)")
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--hasta", type=int, default=9999)
    args = ap.parse_args()

    for ruta in (CSV_ZONAS, CSV_CUADRANTES):
        if not os.path.exists(ruta):
            print(f"No existe {ruta}. Corre antes: python scripts/zonas/clima_zonas.py")
            return 1

    series = series_por_zona(leer(CSV_ZONAS), args.desde, args.hasta)
    zonas = sorted(series)
    if len(zonas) != 2:
        print(f"Se esperaban 2 zonas y hay {len(zonas)}: {zonas}")
        return 1
    a, b = zonas
    anios = sorted(set(series[a]) & set(series[b]))
    if len(anios) < 5:
        print(f"Solo {len(anios)} campanas comunes: insuficiente para contrastar H1.")
        return 1
    espacial = dispersion_espacial(leer(CSV_CUADRANTES), args.desde, args.hasta)

    print(f"== H1: separabilidad climatica · {a} vs {b} · campanas {anios[0]}-{anios[-1]} "
          f"({len(anios)}) ==\n")
    cab = f"{'variable':<12}{a[:9]:>10}{b[:9]:>10}{'dif':>9}{'d':>7}{'SD esp.':>9}{'p':>8}{'r':>7}  separa"
    print(cab)
    print("-" * len(cab))

    resultados, medias = {}, {z: {} for z in zonas}
    for feat in FEATURES:
        va = [series[a][y][feat] for y in anios]
        vb = [series[b][y][feat] for y in anios]
        if any(v is None for v in va + vb):
            print(f"{feat:<12}{'sin datos':>53}")
            continue
        ma, mb = mean(va), mean(vb)
        medias[a][feat], medias[b][feat] = ma, mb
        sd_a, sd_b = (pstdev(va) if len(va) > 1 else 0.0), (pstdev(vb) if len(vb) > 1 else 0.0)
        sd_comb = ((sd_a ** 2 + sd_b ** 2) / 2) ** 0.5
        dif = ma - mb
        d = dif / sd_comb if sd_comb else None
        sd_esp = mean([espacial.get(a, {}).get(feat, 0.0), espacial.get(b, {}).get(feat, 0.0)])
        separa = bool(d is not None and abs(d) >= D_MINIMO and abs(dif) > sd_esp)
        p = wilcoxon_pareado(va, vb)
        r = correlacion(va, vb)
        resultados[feat] = {
            "media": {a: round(ma, 2), b: round(mb, 2)},
            "sd_interanual": {a: round(sd_a, 2), b: round(sd_b, 2)},
            "diferencia": round(dif, 2), "d": round(d, 2) if d is not None else None,
            "sd_espacial_media": round(sd_esp, 2), "p_wilcoxon": p, "r_entre_zonas": r,
            "separa": separa, "clave": feat in CLAVE,
        }
        marca = "SI" if separa else "no"
        if feat in CLAVE:
            marca += " *"
        print(f"{feat:<12}{ma:>10.1f}{mb:>10.1f}{dif:>9.1f}"
              f"{(d if d is not None else float('nan')):>7.2f}{sd_esp:>9.1f}"
              f"{(p if p is not None else float('nan')):>8.3f}{(r if r is not None else float('nan')):>7.2f}  {marca}")

    claves_ok = [f for f in CLAVE if resultados.get(f, {}).get("separa")]
    cumple = len(claves_ok) >= CLAVES_NECESARIAS
    print(f"\n* variables clave. Criterio: |d| >= {D_MINIMO} y |dif| > SD espacial; "
          f"H1 requiere >= {CLAVES_NECESARIAS} de {len(CLAVE)} claves.")
    print(f"Claves que separan: {len(claves_ok)}/{len(CLAVE)} {claves_ok}")
    print(f"\nVEREDICTO H1: {'SE CUMPLE' if cumple else 'NO SE CUMPLE'}")

    fuera = ood_vs_nepena(medias)
    if fuera:
        print("\nOOD vs el entrenamiento de Nepena (media de la zona fuera del rango visto):")
        for zona in zonas:
            items = fuera.get(zona, [])
            print(f"  {zona}: {len(items)}/{len(FEATURES)} variables fuera" +
                  (" -> " + ", ".join(f"{i['variable']} {i['posicion']}" for i in items) if items else ""))

    png = figura(series, zonas, FIGURA)
    salida = {
        "generado": date.today().isoformat(),
        "zonas": zonas, "campanas": [anios[0], anios[-1]], "n_campanas": len(anios),
        "criterio": {"variables_clave": CLAVE, "d_minimo": D_MINIMO,
                     "claves_necesarias": CLAVES_NECESARIAS,
                     "regla": "|d| >= d_minimo y |diferencia| > SD espacial media"},
        "resultados": resultados,
        "claves_que_separan": claves_ok,
        "h1_se_cumple": cumple,
        "ood_vs_nepena": fuera,
    }
    with open(SALIDA, "w", encoding="utf-8") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=2)
    print(f"\nGuardado: {os.path.relpath(SALIDA, RAIZ)}")
    if png:
        print(f"Guardado: {os.path.relpath(png, RAIZ)}")
    else:
        print("(sin figura: matplotlib no esta instalado)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
