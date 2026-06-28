"""
Migración: tabla puente `lote_campana` (participación de lotes por campaña).

- Crea la tabla `lote_campana` (vía db.create_all, que solo crea las faltantes).
- Backfill NO destructivo: asocia cada lote a las campañas donde ya tiene datos
  (registro agronómico, predicción, cosecha o sincronización climática). Así nada de
  lo que hoy es visible desaparece; a partir de aquí cada campaña gestiona su propio
  set de lotes.

Idempotente: re-ejecutarlo no duplica asociaciones (UNIQUE lote_id+campana_id).

Uso (desde sistema_palta/):  python scripts/migrar_lote_campana.py
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import (
    db, Lote, LoteCampana, RegistroAgronomico, Prediccion, ResultadoCosecha, ClimaSync,
)


def pares_existentes():
    """Conjunto de (lote_id, campana_id) presentes en cualquier tabla hija por campaña."""
    pares = set()
    for modelo in (RegistroAgronomico, Prediccion, ResultadoCosecha, ClimaSync):
        for lote_id, campana_id in db.session.query(modelo.lote_id, modelo.campana_id).distinct():
            if lote_id is not None and campana_id is not None:
                pares.add((lote_id, campana_id))
    return pares


def main():
    app = create_app()
    with app.app_context():
        db.create_all()  # crea lote_campana si falta (no altera tablas existentes)

        # Asociaciones ya existentes (para idempotencia)
        ya = {(lc.lote_id, lc.campana_id) for lc in LoteCampana.query.all()}
        en_prod = {l.id: bool(l.en_produccion) for l in Lote.query.all()}

        creadas = 0
        for lote_id, campana_id in sorted(pares_existentes()):
            if (lote_id, campana_id) in ya:
                continue
            db.session.add(LoteCampana(
                lote_id=lote_id, campana_id=campana_id,
                en_produccion=en_prod.get(lote_id, True),
            ))
            ya.add((lote_id, campana_id))
            creadas += 1

        db.session.commit()
        total = LoteCampana.query.count()
        print(f"✓ Backfill completo: {creadas} asociaciones nuevas. "
              f"Total lote_campana = {total}.")
        # Resumen por campaña
        from app.models import Campana
        for c in Campana.query.order_by(Campana.id).all():
            n = LoteCampana.query.filter_by(campana_id=c.id).count()
            print(f"  · Campaña {c.id} «{c.nombre}» → {n} lote(s)")


if __name__ == "__main__":
    main()
