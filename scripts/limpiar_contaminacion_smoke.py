"""
Limpieza puntual: borra las filas de PRUEBA que mis smoke tests escribieron por error
en instance/palta.db (config.py tiene la ruta hardcodeada, el override no aplicó).

Borra SOLO: fincas 2,3 · lotes 8,9 · campañas 4,5,6,7 y sus filas dependientes.
NO toca: campañas 1 y 3, finca 1, lotes 1-7, ni el backfill legítimo de lote_campana.

Hace BACKUP de la BD antes de borrar. Uso (desde sistema_palta/):
    python scripts/limpiar_contaminacion_smoke.py
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "instance", "palta.db")

CAMP = (4, 5, 6, 7)   # campañas de prueba
LOTE = (8, 9)         # lotes de prueba
FINCA = (2, 3)        # fincas de prueba


def main():
    bak = DB + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(DB, bak)
    print(f"Backup creado: {bak}")

    db = sqlite3.connect(DB)
    c = db.cursor()
    total = 0

    def borrar(sql, params):
        nonlocal total
        try:
            c.execute(sql, params)
            print(f"  {sql.split('FROM')[1].split('WHERE')[0].strip():<24} -> {c.rowcount}")
            total += c.rowcount
        except sqlite3.OperationalError as e:
            print(f"  (skip) {e}")

    # Hijos por campaña de prueba (orden FK-seguro)
    for t in ["lote_campana", "clima_sync", "registro_agronomico", "prediccion",
              "resultado_cosecha", "inventario", "alerta", "plan_cosecha"]:
        borrar(f"DELETE FROM {t} WHERE campana_id IN (?,?,?,?)", CAMP)
    # Hijos por lote de prueba
    for t in ["lote_campana", "clima_sync", "registro_agronomico", "prediccion",
              "resultado_cosecha"]:
        borrar(f"DELETE FROM {t} WHERE lote_id IN (?,?)", LOTE)
    # Entidades de prueba
    borrar("DELETE FROM lote WHERE id IN (?,?)", LOTE)
    borrar("DELETE FROM finca WHERE id IN (?,?)", FINCA)
    borrar("DELETE FROM campana WHERE id IN (?,?,?,?)", CAMP)

    db.commit()
    print(f"--- {total} filas de prueba borradas ---")
    print("Campañas restantes:", [r[0] for r in c.execute("SELECT id FROM campana")])
    print("Fincas restantes:  ", [r[0] for r in c.execute("SELECT id FROM finca")])
    print("Lotes restantes:   ", [r[0] for r in c.execute("SELECT id FROM lote")])
    print("lote_campana:      ", c.execute("SELECT COUNT(*) FROM lote_campana").fetchone()[0], "filas (backfill legítimo)")
    db.close()


if __name__ == "__main__":
    main()
