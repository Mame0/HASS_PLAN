"""Pruebas del esquema de datos: jerarquia Finca -> Lote y borrado en cascada."""
import json

from sqlalchemy import inspect

from app.models import db, Finca, Lote
from app.services.geo import resumen

POLY = {"type": "Polygon", "coordinates": [[
    [-71.92, -16.59], [-71.919, -16.59], [-71.919, -16.589], [-71.92, -16.589], [-71.92, -16.59],
]]}


def test_esquema_finca_reemplaza_campo(app):
    with app.app_context():
        tablas = set(inspect(db.engine).get_table_names())
        assert "finca" in tablas
        assert "campo" not in tablas
        cols_lote = {c["name"] for c in inspect(db.engine).get_columns("lote")}
        assert {"finca_id", "geometria", "latitud", "longitud"} <= cols_lote
        cols_finca = {c["name"] for c in inspect(db.engine).get_columns("finca")}
        assert {"geometria", "centro_lat", "centro_lon"} <= cols_finca


def test_lote_deriva_centroide_y_area(app):
    with app.app_context():
        f = Finca(nombre="Chacra La Joya", distrito="La Joya, Arequipa")
        db.session.add(f)
        db.session.flush()
        r = resumen(json.dumps(POLY))
        lote = Lote(finca_id=f.id, nombre="Lote 1", geometria=json.dumps(POLY),
                    area_ha=r["area_ha"], latitud=r["centro_lat"], longitud=r["centro_lon"])
        db.session.add(lote)
        db.session.commit()
        leido = Lote.query.first()
        assert leido.area_ha > 0
        assert leido.finca.nombre == "Chacra La Joya"


def test_borrado_en_cascada_finca_borra_lotes(app):
    with app.app_context():
        f = Finca(nombre="F", distrito="x")
        db.session.add(f)
        db.session.flush()
        db.session.add(Lote(finca_id=f.id, nombre="L1", area_ha=1.0))
        db.session.commit()
        assert Lote.query.count() == 1
        db.session.delete(f)
        db.session.commit()
        assert Lote.query.count() == 0
