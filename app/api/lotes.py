"""
Lotes (parcelas dentro de una finca — Módulo 3).

El agricultor los dibuja en el mapa: si manda un POLÍGONO GeoJSON, el backend deriva
centroide + área; si manda un PUNTO, usa el punto como centroide y el área va a mano.

Los lotes son FÍSICOS (cuelgan de la finca), pero su PARTICIPACIÓN es por campaña
(tabla puente LoteCampana). La UI trabaja siempre con la lista de una campaña.

GET    /campanas/<id>/lotes          -> lotes que participan en la campaña
POST   /campanas/<id>/lotes/<loteId> -> asocia un lote EXISTENTE a la campaña
DELETE /campanas/<id>/lotes/<loteId> -> quita el lote de la campaña (+ sus datos de esa campaña)

GET    /fincas/<id>/lotes -> todos los lotes físicos de la finca (catálogo, sin filtrar)
POST   /fincas/<id>/lotes -> crea un lote y lo asocia a la campaña indicada (campana_id)
GET    /lotes/<id>        -> un lote
PUT    /lotes/<id>        -> edita (si cambia la geometría, re-deriva)
DELETE /lotes/<id>        -> elimina el lote FÍSICO y todo su histórico (cascada)
"""
import json

from flask import Blueprint, jsonify, request, abort

from app.models import db, Finca, Lote, Campana
from app.services import validacion as v
from app.services import geo
from app.services.prediccion import historial_lote
from app.api._common import (
    serialize_lote, get_campana, bloquear_si_cerrada,
    asociar_lote, desasociar_lote, lotes_de_campana, get_lote_campana,
)

bp = Blueprint("lotes", __name__)


def _resolver_geo(data, area_actual=None):
    """
    Devuelve (geometria_texto, lat, lon, area_ha) a partir del payload.
    - Polígono -> área y centroide derivados.
    - Punto    -> centroide = punto; área del payload (obligatoria).
    - Sin geometría -> área del payload; lat/lon opcionales.
    Lanza ValueError (área inválida) o aborta 400 (GeoJSON inválido).
    """
    geom = data.get("geometria")
    if geom is not None:
        try:
            res = geo.resumen(geom)
        except (ValueError, KeyError, TypeError):
            abort(400, description="Geometría GeoJSON inválida.")
        texto = json.dumps(geom)
        if res["area_ha"] > 0:                       # polígono: área derivada
            return texto, res["centro_lat"], res["centro_lon"], res["area_ha"]
        # punto: necesita área manual
        area = v.numero_positivo(data.get("area_ha", area_actual), "area_ha")
        return texto, res["centro_lat"], res["centro_lon"], area
    # sin geometría
    area = v.numero_positivo(data.get("area_ha", area_actual), "area_ha")
    return None, data.get("latitud"), data.get("longitud"), area


@bp.get("/campanas/<int:campana_id>/lotes")
def listar_campana(campana_id):
    """Lotes que PARTICIPAN en la campaña (lista canónica que consume la UI)."""
    Campana.query.get_or_404(campana_id)
    lotes = lotes_de_campana(campana_id)
    return jsonify([serialize_lote(l, get_lote_campana(l.id, campana_id)) for l in lotes])


@bp.post("/campanas/<int:campana_id>/lotes/<int:lote_id>")
def asociar(campana_id, lote_id):
    """Asocia un lote EXISTENTE (de la finca) a la campaña. Idempotente."""
    campana = Campana.query.get_or_404(campana_id)
    bloquear_si_cerrada(campana)
    lote = Lote.query.get_or_404(lote_id)
    lc = asociar_lote(lote, campana)  # hereda el estado productivo del lote físico
    return jsonify(serialize_lote(lote, lc)), 201


@bp.delete("/campanas/<int:campana_id>/lotes/<int:lote_id>")
def desasociar(campana_id, lote_id):
    """Quita el lote de la campaña: borra su participación y sus datos EN esa campaña.

    El lote físico y su histórico en otras campañas NO se tocan.
    """
    campana = Campana.query.get_or_404(campana_id)
    bloquear_si_cerrada(campana)
    lote = Lote.query.get_or_404(lote_id)
    if get_lote_campana(lote_id, campana_id) is None:
        abort(404, description="El lote no participa en esta campaña.")
    desasociar_lote(lote, campana)
    return "", 204


@bp.get("/fincas/<int:finca_id>/lotes")
def listar(finca_id):
    """Catálogo de lotes FÍSICOS de la finca (sin filtrar por campaña).

    Útil para 'agregar un lote existente' a una campaña. Si se pasa ?campana_id, cada
    lote indica si ya participa en ella (`en_campana`)."""
    Finca.query.get_or_404(finca_id)
    lotes = Lote.query.filter_by(finca_id=finca_id).order_by(Lote.nombre).all()
    campana_id = request.args.get("campana_id", type=int)
    out = []
    for l in lotes:
        d = serialize_lote(l)
        if campana_id:
            d["en_campana"] = get_lote_campana(l.id, campana_id) is not None
        out.append(d)
    return jsonify(out)


@bp.post("/fincas/<int:finca_id>/lotes")
def crear(finca_id):
    """Crea un lote físico y lo asocia a la campaña de trabajo (campana_id).

    El lote nuevo entra SOLO a esa campaña: no aparece en las demás hasta asociarlo.
    """
    Finca.query.get_or_404(finca_id)
    data = request.get_json(silent=True) or {}
    # Campaña destino: del body, del query, o la activa/primera por defecto. Si no hay
    # ninguna campaña, el lote se crea solo como físico (sin asociación).
    campana = get_campana(data.get("campana_id") or request.args.get("campana_id", type=int))
    bloquear_si_cerrada(campana)
    # Separación por finca: si hay campaña destino, debe ser de ESTA finca (validar
    # ANTES de crear el lote para no dejar un lote huérfano en una request fallida).
    if campana and campana.finca_id != finca_id:
        abort(400, description="La campaña es de otra finca; el lote debe crearse en la finca de la campaña.")
    try:
        nombre = v.texto_requerido(data.get("nombre"), "nombre")
        ano = v.entero_no_negativo(data.get("ano_plantacion"), "ano_plantacion")
        geometria, lat, lon, area = _resolver_geo(data)
    except ValueError as e:
        abort(400, description=str(e))
    lote = Lote(
        finca_id=finca_id, nombre=nombre, area_ha=area,
        variedad=data.get("variedad", "Hass"), ano_plantacion=ano,
        densidad_plantas_ha=data.get("densidad_plantas_ha"),
        en_produccion=data.get("en_produccion", True),
        geometria=geometria, latitud=lat, longitud=lon,
        fuente_preferida_id=data.get("fuente_preferida_id"),
    )
    db.session.add(lote)
    db.session.commit()
    lc = asociar_lote(lote, campana, en_produccion=data.get("en_produccion", True)) if campana else None
    return jsonify(serialize_lote(lote, lc)), 201


@bp.get("/lotes/<int:lote_id>")
def obtener(lote_id):
    return jsonify(serialize_lote(Lote.query.get_or_404(lote_id)))


@bp.get("/lotes/<int:lote_id>/historial")
def historial(lote_id):
    """Historial productivo del lote (Tn/Ha por campaña: real si hay cosecha, si no predicho)."""
    lote = Lote.query.get_or_404(lote_id)
    return jsonify(historial_lote(lote))


@bp.put("/lotes/<int:lote_id>")
def editar(lote_id):
    lote = Lote.query.get_or_404(lote_id)
    data = request.get_json(silent=True) or {}
    try:
        if "nombre" in data:
            lote.nombre = v.texto_requerido(data.get("nombre"), "nombre")
        if "ano_plantacion" in data:
            lote.ano_plantacion = v.entero_no_negativo(data.get("ano_plantacion"), "ano_plantacion")
        if "geometria" in data or "area_ha" in data:
            geometria, lat, lon, area = _resolver_geo(data, area_actual=lote.area_ha)
            if "geometria" in data:
                lote.geometria, lote.latitud, lote.longitud = geometria, lat, lon
            lote.area_ha = area
    except ValueError as e:
        abort(400, description=str(e))
    for campo in ("variedad", "en_produccion", "fuente_preferida_id", "densidad_plantas_ha"):
        if campo in data:
            setattr(lote, campo, data.get(campo))
    db.session.commit()
    return jsonify(serialize_lote(lote))


@bp.delete("/lotes/<int:lote_id>")
def eliminar(lote_id):
    lote = Lote.query.get_or_404(lote_id)
    db.session.delete(lote)
    db.session.commit()
    return "", 204
