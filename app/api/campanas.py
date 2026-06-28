"""
Campañas agrícolas (Módulo 2). Cada campaña pertenece a UNA finca.

GET    /campanas?finca_id=X   -> lista (filtra por finca si se indica)
POST   /campanas              -> crea (requiere finca_id; estado inicial 'borrador')
PUT    /campanas/<id>         -> edita
POST   /campanas/<id>/activar -> la deja activa (cierra otra activa DE LA MISMA FINCA)
POST   /campanas/<id>/cerrar  -> la deja cerrada (histórico consultable)
DELETE /campanas/<id>         -> elimina (cascada a registros/predicciones/...)
"""
from flask import Blueprint, jsonify, request, abort

from app.models import db, Campana, Finca
from app.services import validacion as v
from app.api._common import serialize_campana, asociar_lote, lotes_de_campana

bp = Blueprint("campanas", __name__)


@bp.get("/campanas")
def listar():
    q = Campana.query
    finca_id = request.args.get("finca_id", type=int)
    if finca_id is not None:
        q = q.filter(Campana.finca_id == finca_id)
    campanas = q.order_by(Campana.fecha_inicio.desc()).all()
    return jsonify([serialize_campana(c) for c in campanas])


@bp.post("/campanas")
def crear():
    data = request.get_json(silent=True) or {}
    try:
        nombre = v.texto_requerido(data.get("nombre"), "nombre")
        di, df = v.ventana_campana(data.get("fecha_inicio"), data.get("fecha_fin"))
    except ValueError as e:
        abort(400, description=str(e))
    # La campaña debe pertenecer a una finca (que exista y sea del tenant — RLS lo
    # garantiza: get_or_404 no la encuentra si es de otro productor).
    finca_id = data.get("finca_id")
    if finca_id is None:
        abort(400, description="finca_id es obligatorio: la campaña pertenece a una finca.")
    Finca.query.get_or_404(finca_id, description="Finca no encontrada.")
    c = Campana(nombre=nombre, finca_id=finca_id, fecha_inicio=di, fecha_fin=df, estado="borrador")
    db.session.add(c)
    db.session.commit()
    # Carry-over opcional: copiar el set de lotes de otra campaña (sin sus datos, solo
    # qué lotes participan). Permite arrancar la campaña nueva con los lotes de la anterior.
    copiar_de = data.get("copiar_lotes_de")
    if copiar_de:
        for lote in lotes_de_campana(copiar_de):
            asociar_lote(lote, c, en_produccion=lote.en_produccion)
    return jsonify(serialize_campana(c)), 201


@bp.put("/campanas/<int:campana_id>")
def editar(campana_id):
    c = Campana.query.get_or_404(campana_id)
    data = request.get_json(silent=True) or {}
    try:
        if "nombre" in data:
            c.nombre = v.texto_requerido(data.get("nombre"), "nombre")
        if "fecha_inicio" in data or "fecha_fin" in data:
            c.fecha_inicio, c.fecha_fin = v.ventana_campana(
                data.get("fecha_inicio", c.fecha_inicio),
                data.get("fecha_fin", c.fecha_fin))
    except ValueError as e:
        abort(400, description=str(e))
    db.session.commit()
    return jsonify(serialize_campana(c))


@bp.post("/campanas/<int:campana_id>/activar")
def activar(campana_id):
    c = Campana.query.get_or_404(campana_id)
    # Solo una campaña activa a la vez POR FINCA: cerrar otra activa de la misma finca.
    for otra in Campana.query.filter(
        Campana.finca_id == c.finca_id, Campana.estado == "activa", Campana.id != c.id
    ).all():
        otra.estado = "cerrada"
    # Cerrar PRIMERO (flush) antes de activar, para no chocar con el índice único
    # parcial uq_campana_activa_finca (que garantiza 1 activa por finca en el motor).
    db.session.flush()
    c.estado = "activa"
    db.session.commit()
    return jsonify(serialize_campana(c))


@bp.post("/campanas/<int:campana_id>/cerrar")
def cerrar(campana_id):
    c = Campana.query.get_or_404(campana_id)
    c.estado = "cerrada"
    db.session.commit()
    return jsonify(serialize_campana(c))


@bp.delete("/campanas/<int:campana_id>")
def eliminar(campana_id):
    c = Campana.query.get_or_404(campana_id)
    db.session.delete(c)
    db.session.commit()
    return "", 204
