"""Utilidades compartidas por los blueprints de la API: metadatos de variables, lookups y serializadores."""
import json

from flask import abort

from app.models import (
    db, Campana, Finca, Lote, LoteCampana, RegistroAgronomico, ResultadoCosecha,
    ClimaSync, FuenteDatos, Prediccion, PlanCosecha, SemanaCosecha,
    PlanManoObra, PlanTransporte, Inventario, LogisticaSemanal, Alerta,
)


def _geojson(texto):
    """Parsea la geometría guardada como texto a objeto GeoJSON (o None)."""
    if not texto:
        return None
    try:
        return json.loads(texto)
    except (ValueError, TypeError):
        return None

# Metadatos de las 17 variables que muestra el front (5 manual + 12 API).
# source: manual = la ingresa el productor · api = la calcula el motor climático.
VAR_META = {
    # ---- Manuales ----
    "frutos_arbol": {"label": "Frutos / árbol",      "unit": "und",   "group": "Productividad",     "source": "manual"},
    "peso_fruto":   {"label": "Peso del fruto",      "unit": "g",     "group": "Productividad",     "source": "manual"},
    "riego_m3ha":   {"label": "Riego aplicado",      "unit": "m³/Ha", "group": "Manejo",            "source": "manual"},
    "edad_campo":   {"label": "Edad del campo",      "unit": "años",  "group": "Manejo",            "source": "manual"},
    "edad_prod":    {"label": "Edad productiva",     "unit": "años",  "group": "Manejo",            "source": "manual"},
    # ---- Automáticas (API meteorológica) ----
    "hfrio_19":     {"label": "Horas frío < 19°C",   "unit": "h",     "group": "Térmicas — Frío",   "source": "api"},
    "hfrio_15":     {"label": "Horas frío < 15°C",   "unit": "h",     "group": "Térmicas — Frío",   "source": "api"},
    "hfrio_14":     {"label": "Horas frío < 14°C",   "unit": "h",     "group": "Térmicas — Frío",   "source": "api"},
    "hfrio_14_19":  {"label": "Horas frío 14–19°C",  "unit": "h",     "group": "Térmicas — Frío",   "source": "api"},
    "hac_20_25":    {"label": "Horas calor 20–25°C", "unit": "h",     "group": "Térmicas — Calor",  "source": "api"},
    "hac_25":       {"label": "Horas calor > 25°C",  "unit": "h",     "group": "Térmicas — Calor",  "source": "api"},
    "t_prom":       {"label": "T° promedio",         "unit": "°C",    "group": "Clima",             "source": "api"},
    "t_min":        {"label": "T° mínima",           "unit": "°C",    "group": "Clima",             "source": "api"},
    "t_max":        {"label": "T° máxima",           "unit": "°C",    "group": "Clima",             "source": "api"},
    "humedad":      {"label": "Humedad relativa",    "unit": "%",     "group": "Clima",             "source": "api"},
    "lluvia":       {"label": "Lluvia",              "unit": "mm",    "group": "Clima",             "source": "api"},
    "eto":          {"label": "ETO",                 "unit": "mm",    "group": "Clima",             "source": "api"},
}

# Las 2 manuales de productividad viven en ResultadoCosecha (muestreo pre-cosecha);
# el resto de manuales y todas las climáticas viven en RegistroAgronomico.
HARVEST_KEYS = {"frutos_arbol", "peso_fruto"}
API_KEYS = RegistroAgronomico.CLIMATE_FEATURES


def get_campana(campana_id=None):
    """Devuelve la campaña por id, o la activa, o la primera disponible."""
    if campana_id:
        return db.session.get(Campana, campana_id)
    return (Campana.query.filter_by(estado="activa").first()
            or Campana.query.first())


def get_campana_o_404(campana_id):
    """Campaña por id o aborta con HTTP 404. Helper compartido por los blueprints."""
    campana = get_campana(campana_id)
    if campana is None:
        abort(404, description="Campaña no encontrada.")
    return campana


def bloquear_si_cerrada(campana):
    """Inmutabilidad del histórico: rechaza escrituras (409) en campañas cerradas.

    Las transiciones de estado de la campaña (activar/cerrar/eliminar) NO usan este
    guard; solo los módulos dependientes (variables, plan, M6/M7/M8, predicción, alertas).
    """
    if campana is not None and campana.estado == "cerrada":
        abort(409, description="La campaña está cerrada (histórico inmutable). "
                               "Actívala para poder modificar sus datos.")
    return campana


def get_or_create_registro(lote, campana, create=True):
    """Obtiene el RegistroAgronomico de (lote, campaña); lo crea vacío si no existe."""
    reg = RegistroAgronomico.query.filter_by(
        lote_id=lote.id, campana_id=campana.id).first()
    if reg is None and create:
        reg = RegistroAgronomico(lote_id=lote.id, campana_id=campana.id)
        db.session.add(reg)
        db.session.commit()
    return reg


def get_lote_campana(lote_id, campana_id):
    """Participación de un lote en una campaña (LoteCampana) o None."""
    return LoteCampana.query.filter_by(lote_id=lote_id, campana_id=campana_id).first()


def validar_lote_en_campana(lote, campana):
    """
    Garantiza la integridad lote<->campaña antes de operar (predicción, variables,
    clima, cosecha): el lote debe ser de la MISMA finca que la campaña y PARTICIPAR
    en ella (existir su LoteCampana). Evita escribir datos cruzados entre fincas o
    en campañas a las que el lote no pertenece.
    """
    if lote.finca_id != campana.finca_id:
        abort(400, description="El lote pertenece a otra finca que la campaña.")
    if get_lote_campana(lote.id, campana.id) is None:
        abort(409, description="El lote no participa en esta campaña; agrégalo a la campaña primero.")


def asociar_lote(lote, campana, en_produccion=None):
    """Asocia un lote (físico) a una campaña. Idempotente: si ya participa, no duplica."""
    # Separación estricta por finca: la campaña y el lote deben ser de la MISMA finca.
    if lote.finca_id != campana.finca_id:
        abort(400, description="El lote es de otra finca; una campaña solo admite lotes de su finca.")
    lc = get_lote_campana(lote.id, campana.id)
    if lc is None:
        lc = LoteCampana(
            lote_id=lote.id, campana_id=campana.id,
            en_produccion=lote.en_produccion if en_produccion is None else en_produccion,
        )
        db.session.add(lc)
        db.session.commit()
    return lc


def desasociar_lote(lote, campana):
    """
    Quita un lote de una campaña: borra la participación y TODOS los datos de ese lote
    EN ESA campaña (registro/variables, predicción, cosecha, clima). El lote físico y su
    histórico en otras campañas quedan intactos.
    """
    for modelo in (RegistroAgronomico, Prediccion, ResultadoCosecha, ClimaSync):
        modelo.query.filter_by(lote_id=lote.id, campana_id=campana.id).delete()
    LoteCampana.query.filter_by(lote_id=lote.id, campana_id=campana.id).delete()
    db.session.commit()


def lotes_de_campana(campana_id):
    """Lotes que PARTICIPAN en una campaña (vía LoteCampana), ordenados por nombre."""
    return (Lote.query
            .join(LoteCampana, LoteCampana.lote_id == Lote.id)
            .filter(LoteCampana.campana_id == campana_id)
            .order_by(Lote.nombre)
            .all())


def last_sync(lote, campana):
    return (ClimaSync.query
            .filter_by(lote_id=lote.id, campana_id=campana.id)
            .order_by(ClimaSync.fetched_at.desc())
            .first())


def serialize_fuente(f: FuenteDatos):
    return {"id": f.id, "nombre": f.nombre, "tipo": f.tipo,
            "endpoint": f.endpoint, "resolucion": f.resolucion, "activa": f.activa}


def serialize_clima_sync(cs: ClimaSync):
    if cs is None:
        return None
    return {
        "id": cs.id, "lote_id": cs.lote_id, "campana_id": cs.campana_id,
        "fuente": cs.fuente.nombre if cs.fuente else None,
        "ventana": [cs.ventana_inicio.isoformat() if cs.ventana_inicio else None,
                    cs.ventana_fin.isoformat() if cs.ventana_fin else None],
        "fetched_at": cs.fetched_at.isoformat() if cs.fetched_at else None,
        "status": cs.status, "mensaje": cs.mensaje,
    }


def serialize_semana(s: SemanaCosecha):
    return {
        "id": s.id, "numero_semana": s.numero_semana,
        "fecha_inicio": s.fecha_inicio.isoformat() if s.fecha_inicio else None,
        "fecha_fin": s.fecha_fin.isoformat() if s.fecha_fin else None,
        "tn_planificada": s.tn_planificada, "porcentaje": s.porcentaje,
        "tn_real": s.tn_real,
    }


def serialize_plan_cosecha(plan: PlanCosecha):
    if plan is None:
        return None
    semanas = sorted(plan.semanas, key=lambda s: s.numero_semana)
    return {
        "id": plan.id, "campana_id": plan.campana_id,
        "fecha_inicio": plan.fecha_inicio.isoformat() if plan.fecha_inicio else None,
        "semanas_total": plan.semanas_total, "tn_total": plan.tn_total,
        "curva": plan.curva,
        "semanas": [serialize_semana(s) for s in semanas],
    }


def serialize_mano_obra(pmo: PlanManoObra):
    """M6: parámetros del plan de mano de obra + requerimiento por semana."""
    if pmo is None:
        return None
    reqs = sorted(pmo.requerimientos, key=lambda r: r.semana.numero_semana)
    return {
        "plan_cosecha_id": pmo.plan_cosecha_id,
        "rendimiento_jornal": pmo.rendimiento_jornal,
        "tam_cuadrilla": pmo.tam_cuadrilla,
        "cuadrillas_disponibles": pmo.cuadrillas_disponibles,
        "dias_cosecha_semana": pmo.dias_cosecha_semana,
        "semanas": [
            {"semana_id": r.semana_id, "numero_semana": r.semana.numero_semana,
             "tn_planificada": r.semana.tn_planificada,
             "jornales_req": r.jornales_req, "cuadrillas_req": r.cuadrillas_req,
             "deficit": r.deficit}
            for r in reqs
        ],
        "tiene_deficit": any((r.deficit or 0) > 0 for r in reqs),
    }


def serialize_transporte(pt: PlanTransporte):
    """M8: parámetros del plan de transporte + despacho por semana."""
    if pt is None:
        return None
    desp = sorted(pt.despachos, key=lambda d: d.semana.numero_semana)
    return {
        "plan_cosecha_id": pt.plan_cosecha_id,
        "cap_camion_tn": pt.cap_camion_tn,
        "costo_por_viaje": pt.costo_por_viaje,
        "camiones_disponibles": pt.camiones_disponibles,
        "viajes_por_camion_semana": pt.viajes_por_camion_semana,
        "semanas": [
            {"semana_id": d.semana_id, "numero_semana": d.semana.numero_semana,
             "tn_despachadas": d.tn_despachadas, "viajes": d.viajes,
             "camiones": d.camiones, "costo": d.costo, "deficit": d.deficit}
            for d in desp
        ],
        "costo_total": round(sum(d.costo or 0 for d in desp), 2),
        "tiene_deficit": any((d.deficit or 0) > 0 for d in desp),
    }


def serialize_inventario(campana: Campana):
    """M7: lista de materiales disponibles de la campaña."""
    return [
        {"id": i.id, "material": i.material,
         "cantidad_disponible": i.cantidad_disponible,
         "unidad": i.unidad, "consumo_por_tn": i.consumo_por_tn}
        for i in campana.inventario
    ]


def serialize_logistica(plan: PlanCosecha):
    """M7: requerimiento de materiales por semana (pico semanal vs stock)."""
    if plan is None:
        return None
    semanas = sorted(plan.semanas, key=lambda s: s.numero_semana)
    semana_ids = [s.id for s in semanas]
    filas = (LogisticaSemanal.query
             .filter(LogisticaSemanal.semana_id.in_(semana_ids)).all()
             if semana_ids else [])
    por_semana = {}
    for f in filas:
        por_semana.setdefault(f.semana_id, []).append(f)
    return {
        "plan_cosecha_id": plan.id,
        "semanas": [
            {"semana_id": s.id, "numero_semana": s.numero_semana,
             "tn_planificada": s.tn_planificada,
             "materiales": [
                 {"material": f.material, "cantidad_requerida": f.cantidad_requerida,
                  "deficit": f.deficit}
                 for f in por_semana.get(s.id, [])
             ]}
            for s in semanas
        ],
        "tiene_deficit": any((f.deficit or 0) > 0 for f in filas),
    }


def serialize_alerta(a: Alerta):
    """M9: alerta de déficit (por semana) para el panel de monitoreo."""
    return {
        "id": a.id, "campana_id": a.campana_id, "semana_id": a.semana_id,
        "tipo": a.tipo, "mensaje": a.mensaje, "modulo_origen": a.modulo_origen,
        "severidad": a.severidad, "estado": a.estado,
        "fecha_creacion": a.fecha_creacion.isoformat() if a.fecha_creacion else None,
    }


def serialize_campana(c: Campana):
    return {
        "id": c.id, "nombre": c.nombre, "finca_id": c.finca_id,
        "fecha_inicio": c.fecha_inicio.isoformat() if c.fecha_inicio else None,
        "fecha_fin": c.fecha_fin.isoformat() if c.fecha_fin else None,
        "estado": c.estado,
    }


def serialize_finca(f: Finca, con_lotes=False):
    # area_total_ha = suma de las áreas de los lotes (se calcula, no se almacena).
    area_total = sum(l.area_ha for l in f.lotes if l.area_ha) or None
    out = {
        "id": f.id, "nombre": f.nombre, "distrito": f.distrito,
        "area_total_ha": round(area_total, 2) if area_total else None,
        "geometria": _geojson(f.geometria),
        "centro_lat": f.centro_lat, "centro_lon": f.centro_lon,
        "n_lotes": len(f.lotes),
    }
    if con_lotes:
        out["lotes"] = [serialize_lote(l) for l in f.lotes]
    return out


def serialize_lote(l: Lote, lc: LoteCampana = None):
    """Serializa un lote. Si se pasa su LoteCampana, `en_produccion` refleja el estado
    EN ESA campaña (no el del lote físico) y se incluye `campana_id`."""
    return {
        "id": l.id, "finca_id": l.finca_id, "nombre": l.nombre,
        "area_ha": l.area_ha, "variedad": l.variedad,
        "ano_plantacion": l.ano_plantacion,
        "densidad_plantas_ha": l.densidad_plantas_ha,
        "en_produccion": lc.en_produccion if lc is not None else l.en_produccion,
        "campana_id": lc.campana_id if lc is not None else None,
        "geometria": _geojson(l.geometria),
        "latitud": l.latitud, "longitud": l.longitud,
        "fuente_preferida_id": l.fuente_preferida_id,
    }


def serialize_prediccion(pred: Prediccion, resultado=None):
    """Serializa una predicción. Si se pasa `resultado` (dict del Predictor),
    agrega la bandera de extrapolación y el detalle OOD con label/unidad."""
    if pred is None:
        return None
    out = {
        "id": pred.id, "lote_id": pred.lote_id, "campana_id": pred.campana_id,
        "tn_ha": round(pred.tn_ha_predicho, 2) if pred.tn_ha_predicho is not None else None,
        "tn_total": round(pred.tn_total_predicho, 2) if pred.tn_total_predicho is not None else None,
        "confianza": round(pred.nivel_confianza, 1) if pred.nivel_confianza is not None else None,
        "intervalo": (
            {"p10": round(pred.intervalo_p10, 2), "p90": round(pred.intervalo_p90, 2)}
            if pred.intervalo_p10 is not None and pred.intervalo_p90 is not None else None
        ),
        "fecha": pred.fecha.isoformat() if pred.fecha else None,
    }
    if resultado is not None:
        out["es_extrapolacion"] = resultado["es_extrapolacion"]
        out["out_of_distribution"] = [
            {**o,
             "label": VAR_META.get(o["variable"], {}).get("label", o["variable"]),
             "unit": VAR_META.get(o["variable"], {}).get("unit", "")}
            for o in resultado["out_of_distribution"]
        ]
    return out


def serialize_variables(lote, campana):
    """Arma la respuesta manual/API de variables para un lote en una campaña."""
    reg = get_or_create_registro(lote, campana)
    cosecha = ResultadoCosecha.query.filter_by(
        lote_id=lote.id, campana_id=campana.id).first()
    overrides = {o.var_key for o in reg.overrides}
    sync = last_sync(lote, campana)
    synced_at = sync.fetched_at.isoformat() if (sync and sync.status == "ok") else None
    fuente = sync.fuente.nombre if (sync and sync.fuente) else None

    manual, api = [], []
    for key, meta in VAR_META.items():
        if key in HARVEST_KEYS:
            value = getattr(cosecha, key) if cosecha else None
        else:
            value = getattr(reg, key, None)
        row = {"key": key, "value": value, **meta}
        if meta["source"] == "api":
            row.update({"synced_at": synced_at, "fuente": fuente,
                        "is_override": key in overrides,
                        "status": "override" if key in overrides
                                  else ("ok" if value is not None else "pendiente")})
            api.append(row)
        else:
            manual.append(row)

    return {
        "lote": {"id": lote.id, "nombre": lote.nombre, "area_ha": lote.area_ha,
                 "latitud": lote.latitud, "longitud": lote.longitud},
        "campana": {"id": campana.id, "nombre": campana.nombre},
        "manual": manual,
        "api": api,
        "last_sync": serialize_clima_sync(sync),
    }
