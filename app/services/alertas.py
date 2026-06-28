"""
Generación de alertas (Fase F6 / Módulo 9).

Convierte los déficits por semana de los módulos derivados (M6/M7/M8) en registros `Alerta`,
**uno por semana con déficit** (decisión jun-2026). Generación **bajo demanda**: se llama desde
el endpoint, no automáticamente en la cascada — el productor regenera tras cambiar el plan.

Idempotente: borra las alertas auto-generadas de la campaña (tipos de déficit) y las recrea
desde el estado vigente del plan. Las alertas creadas a mano por el usuario (otros tipos) no se tocan.
"""
from app.models import db, Alerta, LogisticaSemanal

# Tipos que administra el generador automático (se borran y recrean en cada pasada).
TIPOS_AUTO = ("deficit_personal", "deficit_material", "deficit_transporte")


def _severidad(deficit, requerido):
    """Severidad por magnitud relativa del déficit: baja ≤15% · media ≤40% · alta >40%."""
    if not requerido or requerido <= 0:
        return "media"
    ratio = deficit / requerido
    if ratio <= 0.15:
        return "baja"
    if ratio <= 0.40:
        return "media"
    return "alta"


def generar_alertas(campana):
    """(Re)genera las alertas de déficit de la campaña a partir del plan vigente. Devuelve la lista."""
    Alerta.query.filter(Alerta.campana_id == campana.id,
                        Alerta.tipo.in_(TIPOS_AUTO)).delete(synchronize_session=False)
    db.session.flush()

    plan = campana.plan_cosecha
    if plan is None:
        db.session.commit()
        return []

    sem = {s.id: s.numero_semana for s in plan.semanas}
    nuevas = []

    def add(semana_id, tipo, modulo, deficit, requerido, texto):
        nuevas.append(Alerta(
            campana_id=campana.id, semana_id=semana_id, tipo=tipo, modulo_origen=modulo,
            severidad=_severidad(deficit, requerido),
            mensaje=f"Sem {sem.get(semana_id, '?')}: {texto}"))

    # M6 Mano de obra — falta de cuadrillas
    if plan.plan_mano_obra:
        for r in plan.plan_mano_obra.requerimientos:
            if (r.deficit or 0) > 0:
                add(r.semana_id, "deficit_personal", "mano_obra", r.deficit, r.cuadrillas_req,
                    f"faltan {r.deficit} cuadrilla(s) (req {r.cuadrillas_req}).")

    # M8 Transporte — falta de camiones
    if plan.plan_transporte:
        for d in plan.plan_transporte.despachos:
            if (d.deficit or 0) > 0:
                add(d.semana_id, "deficit_transporte", "transporte", d.deficit, d.camiones,
                    f"faltan {d.deficit} camión(es) (req {d.camiones}).")

    # M7 Logística — falta de material (por semana × material)
    if sem:
        logs = (LogisticaSemanal.query
                .filter(LogisticaSemanal.semana_id.in_(list(sem)),
                        LogisticaSemanal.deficit > 0).all())
        for log in logs:
            add(log.semana_id, "deficit_material", "logistica", log.deficit, log.cantidad_requerida,
                f"faltan {log.deficit:.0f} {log.material}(s) (req {log.cantidad_requerida:.0f}).")

    for a in nuevas:
        db.session.add(a)
    db.session.commit()
    return nuevas


def resolver_alerta(alerta):
    """Marca una alerta como resuelta."""
    alerta.estado = "resuelta"
    db.session.commit()
    return alerta
