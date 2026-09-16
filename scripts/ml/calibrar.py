"""
Recalibra el INTERVALO CONFORMAL del modelo contra la cosecha REAL registrada (F7).

Por que existe aparte de entrenar.py
------------------------------------
`entrenar.py` estima el margen +/-q reservando una campana de NEPENA. Pero el modelo
se despliega en LA JOYA, donde el clima no transfiere: el margen honesto para La Joya
es el que se mide con SU propia cosecha real. Este script hace exactamente eso, sin
reentrenar y sin llamar a ninguna API: lee los pares (Prediccion, ResultadoCosecha)
ya guardados y recalcula q a partir de los residuos observados.

Es la pieza que cierra F7: cada campana cerrada que se carga estrecha (o ensancha)
el intervalo que ve el productor, con datos de su propio fundo.

Uso
---
    python scripts/ml/calibrar.py                    # todas las campanas con cosecha
    python scripts/ml/calibrar.py --campana 3        # solo esa campana
    python scripts/ml/calibrar.py --alpha 0.10       # cobertura del 90% (default 80%)
    python scripts/ml/calibrar.py --dry-run          # calcula y muestra, no escribe

Escribe el bloque "conformal" de app/ml/modelo_meta.json. El servidor cachea el meta
al arrancar: hay que REINICIARLO para que tome el margen nuevo.
"""
import sys
import os
import json
import argparse

sys.stdout.reconfigure(encoding="utf-8")          # consola Windows cp1252 (ver CLAUDE.md)

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RAIZ)

import numpy as np                                                      # noqa: E402

from app import create_app                                              # noqa: E402
from app.models import Prediccion, ResultadoCosecha, Lote, Campana      # noqa: E402

META = os.path.join(RAIZ, "app", "ml", "modelo_meta.json")
MIN_PARES = 5          # por debajo de esto el cuantil no es estimable con garantia


def recolectar(campana_id=None):
    """Pares (predicho, real) de lotes con cosecha real cargada.

    Descarta los ResultadoCosecha con tn_ha_real <= 0: la ruta de variables crea la
    fila con tn_ha_real=0 al guardar solo frutos/arbol (muestreo pre-cosecha), y ese
    cero no es una cosecha, es un registro a medio llenar.
    """
    q = (ResultadoCosecha.query
         .filter(ResultadoCosecha.tn_ha_real > 0))
    if campana_id:
        q = q.filter(ResultadoCosecha.campana_id == campana_id)

    pares = []
    for rc in q.all():
        pred = (Prediccion.query
                .filter_by(lote_id=rc.lote_id, campana_id=rc.campana_id)
                .first())
        if pred is None or pred.tn_ha_predicho is None:
            continue
        lote = Lote.query.get(rc.lote_id)
        camp = Campana.query.get(rc.campana_id)
        pares.append({
            "lote": lote.nombre if lote else f"#{rc.lote_id}",
            "campana": camp.nombre if camp else f"#{rc.campana_id}",
            "predicho": float(pred.tn_ha_predicho),
            "real": float(rc.tn_ha_real),
        })
    return pares


def cuantil_conformal(residuos, alpha):
    """Cuantil conformal con correccion de muestra finita.

    El nivel ceil((n+1)(1-alpha))/n -y no simplemente (1-alpha)- es lo que da la
    garantia de cobertura del conformal split para muestras pequenas.
    """
    n = len(residuos)
    nivel = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(residuos, nivel))


def main():
    ap = argparse.ArgumentParser(description="Recalibra el intervalo conformal con cosecha real.")
    ap.add_argument("--campana", type=int, default=None, help="Limitar a una campana (id)")
    ap.add_argument("--alpha", type=float, default=0.20, help="1-alpha = cobertura (default 0.20 -> 80%%)")
    ap.add_argument("--dry-run", action="store_true", help="No escribir modelo_meta.json")
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        pares = recolectar(args.campana)

    if len(pares) < MIN_PARES:
        print(f"✗ Solo hay {len(pares)} par(es) predicho/real con tn_ha_real > 0.")
        print(f"  Se necesitan al menos {MIN_PARES} para estimar el margen con garantia.")
        print("  Carga mas resultados de cosecha (F7) y vuelve a ejecutar.")
        return 1

    residuos = np.array([abs(p["real"] - p["predicho"]) for p in pares])
    q = cuantil_conformal(residuos, args.alpha)
    cobertura = float((residuos <= q).mean())
    reales = np.array([p["real"] for p in pares])
    predichos = np.array([p["predicho"] for p in pares])

    print("═" * 66)
    print("  CALIBRACIÓN CONFORMAL CONTRA COSECHA REAL")
    print("═" * 66)
    print(f"  Pares predicho/real ......... {len(pares)}")
    print(f"  Campañas .................... {', '.join(sorted({p['campana'] for p in pares}))}")
    print(f"  MAE ......................... {residuos.mean():.2f} Tn/Ha")
    print(f"  Sesgo medio (pred − real) ... {(predichos - reales).mean():+.2f} Tn/Ha")
    print(f"  Cobertura objetivo .......... {1 - args.alpha:.0%}")
    print(f"  Margen conformal q .......... ±{q:.2f} Tn/Ha")
    print(f"  Cobertura en calibración .... {cobertura:.0%}")
    print()
    print(f"  {'lote':<14}{'campaña':<12}{'predicho':>10}{'real':>9}{'|error|':>10}")
    print("  " + "─" * 55)
    for p in sorted(pares, key=lambda x: abs(x["real"] - x["predicho"]), reverse=True)[:12]:
        e = abs(p["real"] - p["predicho"])
        print(f"  {p['lote']:<14}{p['campana']:<12}{p['predicho']:>10.2f}{p['real']:>9.2f}{e:>10.2f}")
    if len(pares) > 12:
        print(f"  … y {len(pares) - 12} más")

    bloque = {
        "q": round(q, 3),
        "cobertura": round(1 - args.alpha, 2),
        "n": len(pares),
        "origen": "cosecha real" + (f" (campaña {args.campana})" if args.campana else ""),
        "cobertura_observada": round(cobertura, 3),
        "mae_observado": round(float(residuos.mean()), 3),
        "sesgo_observado": round(float((predichos - reales).mean()), 3),
    }

    if args.dry_run:
        print("\n  --dry-run: no se escribió modelo_meta.json. Bloque calculado:")
        print("  " + json.dumps(bloque, ensure_ascii=False))
        return 0

    with open(META, encoding="utf-8") as f:
        meta = json.load(f)
    anterior = meta.get("conformal")
    meta["conformal"] = bloque
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    if anterior and anterior.get("q"):
        print(f"\n  Margen anterior: ±{anterior['q']:.2f} Tn/Ha ({anterior.get('origen', '?')})")
    print(f"  Margen nuevo:    ±{q:.2f} Tn/Ha (cosecha real)")
    print(f"\n✓ Escrito en {META}")
    print("  Reinicia el servidor para que el Predictor recargue el metadato.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
