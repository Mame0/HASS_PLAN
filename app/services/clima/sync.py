"""
Orquestador del motor climático.

Para un lote en una campaña: resuelve la ubicación y la ventana de fechas, llama al
proveedor preferido (con NASA POWER como fallback), deriva las 12 variables y las
escribe en el RegistroAgronomico — respetando los overrides manuales — y deja un
registro en ClimaSync (que es además el log del M10).
"""
from datetime import date

from app.models import db, FuenteDatos, ClimaSync, RegistroAgronomico, VariableOverride, utcnow
from app.services.clima.open_meteo import OpenMeteo
from app.services.clima.nasa_power import NasaPower
from app.services.clima.derivar import derivar_features

# Registro de proveedores disponibles por tipo
PROVEEDORES = {
    "open_meteo": OpenMeteo,
    "nasa_power": NasaPower,
}
TIPO_FALLBACK = "nasa_power"


def _fuente_por_tipo(tipo):
    return FuenteDatos.query.filter_by(tipo=tipo).first()


def _registrar(lote, campana, fuente, status, mensaje):
    cs = ClimaSync(
        lote_id=lote.id, campana_id=campana.id,
        fuente_id=fuente.id if fuente else None,
        ventana_inicio=campana.fecha_inicio, ventana_fin=campana.fecha_fin,
        fetched_at=utcnow(), status=status, mensaje=mensaje,
    )
    db.session.add(cs)
    db.session.commit()
    return cs


def sincronizar_clima(registro: RegistroAgronomico, lote, campana):
    """
    Ejecuta la sincronización climática y devuelve el ClimaSync resultante.
    No lanza excepción ante fallos de red/datos: deja status='error' en el log.
    """
    if lote.latitud is None or lote.longitud is None:
        return _registrar(lote, campana, None, "error",
                          "El lote no tiene coordenadas (lat/lon) configuradas.")

    # Campaña futura: aún no existe clima REAL para esa ventana. Las APIs son de
    # archivo histórico (Open-Meteo/NASA POWER) y devuelven 400 ante fechas futuras.
    # Mensaje explícito (en vez del error críptico de la API) -> la ruta responde 502.
    if campana.fecha_inicio and campana.fecha_inicio > date.today():
        return _registrar(
            lote, campana, None, "error",
            f"La campaña «{campana.nombre}» es futura (inicia "
            f"{campana.fecha_inicio.isoformat()}): aún no hay datos climáticos reales "
            f"para esa ventana. La sincronización automática solo aplica a campañas ya "
            f"transcurridas. Ingresa las 12 variables climáticas manualmente, o usa una "
            f"campaña con fechas pasadas para derivarlas desde la API.")

    # Proveedor preferido del lote, o el primario por defecto
    tipo = "open_meteo"
    if lote.fuente_preferida and lote.fuente_preferida.tipo in PROVEEDORES:
        tipo = lote.fuente_preferida.tipo

    serie, usado, nota = None, tipo, ""
    try:
        serie = PROVEEDORES[tipo]().obtener_serie(
            lote.latitud, lote.longitud, campana.fecha_inicio, campana.fecha_fin)
    except Exception as e:
        # Fallback a NASA POWER si el primario falla
        nota = f"Primario {tipo} falló ({e}); fallback {TIPO_FALLBACK}. "
        usado = TIPO_FALLBACK
        try:
            serie = PROVEEDORES[TIPO_FALLBACK]().obtener_serie(
                lote.latitud, lote.longitud, campana.fecha_inicio, campana.fecha_fin)
        except Exception as e2:
            return _registrar(lote, campana, _fuente_por_tipo(tipo), "error",
                              nota + f"Fallback también falló: {e2}")

    try:
        features = derivar_features(serie)
    except ValueError as e:
        return _registrar(lote, campana, _fuente_por_tipo(usado), "error", nota + str(e))

    # Aplicar features respetando overrides manuales del registro
    bloqueadas = {o.var_key for o in registro.overrides}
    aplicadas = 0
    for key, val in features.items():
        if key in bloqueadas:
            continue
        setattr(registro, key, val)
        aplicadas += 1
    db.session.add(registro)

    fuente = _fuente_por_tipo(usado)
    msg = nota + f"{aplicadas} variables actualizadas ({serie.horas()} horas)."
    if bloqueadas:
        msg += f" {len(bloqueadas)} con override (no sobrescritas)."
    return _registrar(lote, campana, fuente, "ok", msg)
